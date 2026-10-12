"""LangGraph (prebuilt ReAct agent) scored through LangChain callbacks.

Callbacks are the surface LangSmith and most LangChain observability
integrations consume (on_tool_start / on_tool_end / on_tool_error).
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import langgraph
from importlib.metadata import version as _v
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.prebuilt import create_react_agent

from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate


class ScriptedChatModel(BaseChatModel):
    cursor: Any = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "tracegap-scripted"

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("async only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        turn = await self.cursor.next_turn()
        if turn.calls:
            msg = AIMessage(
                content="",
                tool_calls=[{"name": c.name, "args": dict(c.args), "id": c.call_id, "type": "tool_call"} for c in turn.calls],
            )
        else:
            msg = AIMessage(content=turn.final or "done")
        return ChatResult(generations=[ChatGeneration(message=msg)])


class Recorder(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.parents: dict[UUID, Optional[UUID]] = {}
        self.events: dict[UUID, TraceEvent] = {}
        self.order = 0

    def _root(self, run_id: UUID) -> str:
        seen = set()
        cur: Optional[UUID] = run_id
        while cur is not None and cur in self.parents and self.parents[cur] is not None and cur not in seen:
            seen.add(cur)
            cur = self.parents[cur]
        return str(cur)

    async def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kw):
        self.parents[run_id] = parent_run_id

    async def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kw):
        self.parents[run_id] = parent_run_id

    async def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, inputs=None, **kw):
        self.parents[run_id] = parent_run_id
        self.order += 1
        name = (serialized or {}).get("name") or kw.get("name")
        args = parse_args(inputs if inputs is not None else input_str)
        call_id = (kw.get("metadata") or {}).get("tool_call_id") or kw.get("tool_call_id")
        self.events[run_id] = TraceEvent(name=name, args=args, status="incomplete", call_id=call_id,
                                         group=self._root(run_id), order=self.order)

    async def on_tool_end(self, output, *, run_id, **kw):
        ev = self.events.get(run_id)
        if ev is None:
            return
        ev.status = "ok"
        content = getattr(output, "content", output)
        ev.output = content
        if getattr(output, "status", None) == "error":
            ev.status = "error"
            ev.error = str(content)
        if ev.call_id is None:
            ev.call_id = getattr(output, "tool_call_id", None)

    async def on_tool_error(self, error, *, run_id, **kw):
        ev = self.events.get(run_id)
        if ev is None:
            return
        ev.status = "error"
        ev.error = f"{type(error).__name__}: {error}"


class LangGraphCallbacks(Adapter):
    framework = "langgraph"
    surface = "callbacks"
    capture = Capture(args=True, output=True, status=True, call_id=True)
    version = f"langgraph {_v('langgraph')}, langchain-core {_v('langchain-core')}"

    async def setup_case(self, scenario, mode):
        self.rec = Recorder()

    def _agent(self, cursor: ScriptCursor, scenario, nested_script, run_index):
        tools = []
        for name in scenario.tools:
            if name == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner_cursor = ScriptCursor(script, ri, nested=True)
                    inner = self._agent(inner_cursor, scenario, None, ri)
                    out = await inner.ainvoke({"messages": [("user", "sub-task")]})
                    return out["messages"][-1].content

                tools.append(make_delegate(run_inner))
            else:
                tools.append(TOOLS[name])
        return create_react_agent(ScriptedChatModel(cursor=cursor), tools)

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        limit = 2 * (scenario.max_model_calls or 12)
        config = {"callbacks": [self.rec], "recursion_limit": limit}
        inp = {"messages": [("user", "go")]}
        if mode == "stream":
            async for _ in agent.astream(inp, config, stream_mode="updates"):
                pass
            return "ok"
        return await agent.ainvoke(inp, config)

    async def collect(self):
        return sorted(self.rec.events.values(), key=lambda e: e.order)
