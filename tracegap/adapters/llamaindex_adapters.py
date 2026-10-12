"""LlamaIndex (FunctionAgent workflow), scored through two surfaces.

* ``events``: ToolCall / ToolCallResult events from ``handler.stream_events()``,
  the documented way to observe a workflow run.
* ``openinference``: TOOL spans from ``openinference-instrumentation-llama-index``.

Modes map to the agent's ``streaming`` flag: ``invoke`` uses
``achat_with_tools``, ``stream`` uses ``astream_chat_with_tools``.
"""

from __future__ import annotations

import asyncio
import json
from importlib.metadata import version as _v

from llama_index.core.agent.workflow import FunctionAgent, ToolCall, ToolCallResult
from llama_index.core.llms import ChatMessage, ChatResponse
from llama_index.core.llms.llm import ToolSelection
try:
    from llama_index.core.llms.mock import MockFunctionCallingLLM
except ImportError:  # llama-index-core < 0.14.10: build the minimal base ourselves
    from llama_index.core.base.llms.types import LLMMetadata
    from llama_index.core.llms.function_calling import FunctionCallingLLM

    class MockFunctionCallingLLM(FunctionCallingLLM):  # type: ignore[no-redef]
        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata(is_function_calling_model=True)

        def _unused(self, *a, **k):
            raise NotImplementedError("scripted LLM only answers chat-with-tools calls")

        chat = stream_chat = complete = stream_complete = _unused

        async def achat(self, *a, **k):
            raise NotImplementedError

        async def astream_chat(self, *a, **k):
            raise NotImplementedError

        async def acomplete(self, *a, **k):
            raise NotImplementedError

        async def astream_complete(self, *a, **k):
            raise NotImplementedError

        def _prepare_chat_with_tools(self, tools, user_msg=None, chat_history=None, **kw):
            return {"messages": chat_history or [], "tools": tools}
from llama_index.core.tools import FunctionTool

from .. import collectors, otel_util
from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate


class ScriptedLLM(MockFunctionCallingLLM):
    """Answers every chat-with-tools call from the TraceGap script."""

    def __init__(self, cursor: ScriptCursor):
        super().__init__()
        object.__setattr__(self, "_cursor", cursor)

    async def achat_with_tools(self, tools, user_msg=None, chat_history=None, **kw):
        turn = await self._cursor.next_turn()
        if not turn.calls:
            return ChatResponse(message=ChatMessage(role="assistant", content=turn.final or "done"))
        calls = [{"id": c.call_id, "name": c.name, "args": dict(c.args)} for c in turn.calls]
        return ChatResponse(message=ChatMessage(role="assistant", content="", additional_kwargs={"tool_calls": calls}))

    async def astream_chat_with_tools(self, tools, user_msg=None, chat_history=None, **kw):
        response = await self.achat_with_tools(tools, user_msg, chat_history, **kw)

        async def gen():
            yield response

        return gen()

    def get_tool_calls_from_response(self, response, error_on_no_tool_call=True, **kw):
        return [ToolSelection(tool_id=c["id"], tool_name=c["name"], tool_kwargs=c["args"])
                for c in response.message.additional_kwargs.get("tool_calls", [])]


class _LlamaBase(Adapter):
    framework = "llamaindex"
    version = f"llama-index-core {_v('llama-index-core')}"

    def _agent(self, cursor, scenario, nested_script, run_index, streaming, name="agent"):
        tools = []
        for t in scenario.tools:
            if t == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri, streaming, "inner")
                    handler = inner.run("sub-task")
                    await self._consume(handler, ri, nested=True)
                    return str(await handler)

                tools.append(FunctionTool.from_defaults(async_fn=make_delegate(run_inner), name="delegate"))
            else:
                fn = TOOLS[t]
                if asyncio.iscoroutinefunction(fn):
                    tools.append(FunctionTool.from_defaults(async_fn=fn, name=t))
                else:
                    tools.append(FunctionTool.from_defaults(fn=fn, name=t))
        return FunctionAgent(name=f"{name}{run_index}", tools=tools, llm=ScriptedLLM(cursor), streaming=streaming,
                             system_prompt="test")

    async def _consume(self, handler, run_index, nested=False):
        async for ev in handler.stream_events():
            self._on_event(ev, run_index)

    def _on_event(self, ev, run_index):
        pass

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index, mode == "stream")
        limit = scenario.max_model_calls or 50
        handler = agent.run("go", max_iterations=limit)
        await self._consume(handler, run_index)
        return str(await handler)


class LlamaIndexEvents(_LlamaBase):
    surface = "events"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        self.events: list[TraceEvent] = []
        self.by_key: dict = {}

    def _on_event(self, ev, run_index):
        if isinstance(ev, ToolCall) and not isinstance(ev, ToolCallResult):
            te = TraceEvent(name=ev.tool_name, args=parse_args(ev.tool_kwargs), status="incomplete",
                            call_id=ev.tool_id, group=f"run{run_index}", order=len(self.events))
            self.events.append(te)
            self.by_key.setdefault((run_index, ev.tool_id), []).append(te)
        elif isinstance(ev, ToolCallResult):
            pending = [e for e in self.by_key.get((run_index, ev.tool_id), []) if e.status == "incomplete"]
            if not pending:
                te = TraceEvent(name=ev.tool_name, args=parse_args(ev.tool_kwargs), status="incomplete",
                                call_id=ev.tool_id, group=f"run{run_index}", order=len(self.events))
                self.events.append(te)
                pending = [te]
            te = pending[0]
            out = ev.tool_output
            if out.is_error:
                te.status, te.error = "error", out.content
            else:
                te.status = "ok"
                te.output = out.raw_output if out.raw_output is not None or out.content in ("", "None") else out.content

    async def collect(self):
        return list(self.events)


def _decode_li_output(value):
    """OpenInference stores LlamaIndex's whole ToolOutput as JSON; a consumer
    reads ``raw_output`` from it (falling back to the text blocks)."""
    if not isinstance(value, str):
        return value
    try:
        d = json.loads(value)
    except Exception:
        return value
    if isinstance(d, dict) and "tool_name" in d:
        if "raw_output" in d:
            return d["raw_output"]
        blocks = d.get("blocks") or []
        return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    return value


class LlamaIndexOpenInference(_LlamaBase):
    surface = "openinference"
    capture = Capture(args=True, output=True, status=True, call_id=False)
    _instrumented = False

    async def setup_case(self, scenario, mode):
        tp, exp = otel_util.provider()
        if not LlamaIndexOpenInference._instrumented:
            from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

            LlamaIndexInstrumentor().instrument(tracer_provider=tp)
            LlamaIndexOpenInference._instrumented = True
        exp.clear()

    async def collect(self):
        evs = collectors.collect("openinference")
        for e in evs:
            e.output = _decode_li_output(e.output)
        return evs
