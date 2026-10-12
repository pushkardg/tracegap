"""AutoGen AgentChat (AssistantAgent), scored through two surfaces.

* ``messages``: the ToolCallRequestEvent / ToolCallExecutionEvent records,
  read from ``TaskResult.messages`` (invoke) or collected from
  ``run_stream()`` as they arrive (stream).
* ``otel``: OpenTelemetry ``execute_tool`` spans emitted by autogen-core.
  These carry the tool name and call id but not arguments or results.
"""

from __future__ import annotations

import inspect
import json
from importlib.metadata import version as _v

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ToolCallExecutionEvent, ToolCallRequestEvent
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

from .. import collectors, otel_util
from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate

MODEL_INFO = {
    "vision": False,
    "function_calling": True,
    "json_output": False,
    "family": "unknown",
    "structured_output": False,
}


class ScriptedClient(ReplayChatCompletionClient):
    def __init__(self, cursor: ScriptCursor):
        super().__init__(["unused"], model_info=MODEL_INFO)
        self._cursor = cursor

    async def create(self, messages, **kwargs):  # type: ignore[override]
        turn = await self._cursor.next_turn()
        usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
        if turn.calls:
            content = [FunctionCall(id=c.call_id, arguments=json.dumps(c.args), name=c.name) for c in turn.calls]
            return CreateResult(finish_reason="function_calls", content=content, usage=usage, cached=False)
        return CreateResult(finish_reason="stop", content=turn.final or "done", usage=usage, cached=False)

    async def create_stream(self, messages, **kwargs):  # type: ignore[override]
        yield await self.create(messages, **kwargs)


class _AutoGenBase(Adapter):
    framework = "autogen"
    version = f"autogen-agentchat {_v('autogen-agentchat')}, autogen-core {_v('autogen-core')}"

    def _agent(self, cursor, scenario, nested_script, run_index, name="agent"):
        tools = []
        for t in scenario.tools:
            if t == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri, name="inner")
                    res = await inner.run(task="sub-task")
                    return res.messages[-1].to_text()

                tools.append(make_delegate(run_inner))
            else:
                tools.append(TOOLS[t])
        kwargs = {}
        # max_tool_iterations arrived in 0.7; earlier versions stop after one tool round,
        # which the ground truth records as it happens.
        if "max_tool_iterations" in inspect.signature(AssistantAgent.__init__).parameters:
            kwargs["max_tool_iterations"] = scenario.max_model_calls or 50
        return AssistantAgent(f"{name}{run_index}", model_client=ScriptedClient(cursor), tools=tools, **kwargs)


def _events_from_messages(msgs, group: str, start_order: int) -> list[TraceEvent]:
    out: list[TraceEvent] = []
    by_id: dict[str, list[TraceEvent]] = {}
    order = start_order
    for m in msgs:
        if isinstance(m, ToolCallRequestEvent):
            for fc in m.content:
                order += 1
                ev = TraceEvent(name=fc.name, args=parse_args(fc.arguments), status="incomplete",
                                call_id=fc.id, group=group, order=order)
                out.append(ev)
                by_id.setdefault(fc.id, []).append(ev)
        elif isinstance(m, ToolCallExecutionEvent):
            for res in m.content:
                pending = [e for e in by_id.get(res.call_id, []) if e.status == "incomplete"]
                if not pending:
                    continue
                ev = pending[0]
                if res.is_error:
                    ev.status = "error"
                    ev.error = res.content
                else:
                    ev.status = "ok"
                    ev.output = res.content
    return out


class AutoGenMessages(_AutoGenBase):
    surface = "messages"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        self.collected: dict[int, list] = {}

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        if mode == "stream":
            sink = self.collected.setdefault(run_index, [])
            async for m in agent.run_stream(task="go"):
                if not isinstance(m, TaskResult):
                    sink.append(m)
            return "ok"
        res = await agent.run(task="go")
        self.collected[run_index] = list(res.messages)
        return "ok"

    async def collect(self):
        out: list[TraceEvent] = []
        for ri, msgs in self.collected.items():
            out += _events_from_messages(msgs, f"run{ri}", len(out))
        return out


class AutoGenOtel(_AutoGenBase):
    surface = "otel"
    capture = Capture(args=False, output=False, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        otel_util.provider()[1].clear()

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        if mode == "stream":
            async for _ in agent.run_stream(task="go"):
                pass
            return "ok"
        await agent.run(task="go")
        return "ok"

    async def collect(self):
        return collectors.collect("genai")
