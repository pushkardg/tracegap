"""Pydantic AI, scored through two surfaces.

* ``history``: the run's message history. In invoke mode this is read via
  ``capture_run_messages()`` (the documented way to get messages even when a
  run fails); in stream mode it is the ``run_stream_events()`` event stream,
  collected as it arrives.
* ``otel``: OpenTelemetry ``execute_tool`` spans from the built-in
  ``Instrumentation`` capability.
"""

from __future__ import annotations

import json
from importlib.metadata import version as _v

from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.capabilities.instrumentation import Instrumentation
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.usage import UsageLimits

from .. import collectors, otel_util
from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate


def scripted_model(cursor: ScriptCursor) -> FunctionModel:
    async def respond(messages, info):
        turn = await cursor.next_turn()
        if turn.calls:
            return ModelResponse(parts=[ToolCallPart(c.name, dict(c.args), tool_call_id=c.call_id) for c in turn.calls])
        return ModelResponse(parts=[TextPart(turn.final or "done")])

    async def stream(messages, info):
        turn = await cursor.next_turn()
        if turn.calls:
            yield {
                i: DeltaToolCall(name=c.name, json_args=json.dumps(c.args), tool_call_id=c.call_id)
                for i, c in enumerate(turn.calls)
            }
        else:
            yield turn.final or "done"

    return FunctionModel(respond, stream_function=stream)


class _PydanticBase(Adapter):
    framework = "pydantic-ai"
    version = f"pydantic-ai-slim {_v('pydantic-ai-slim')}"

    def _capabilities(self):
        return []

    def _agent(self, cursor, scenario, nested_script, run_index):
        tools = []
        for name in scenario.tools:
            if name == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri)
                    res = await inner.run("sub-task")
                    return res.output

                tools.append(make_delegate(run_inner))
            else:
                tools.append(TOOLS[name])
        return Agent(scripted_model(cursor), tools=tools, capabilities=self._capabilities())

    def _limits(self, scenario):
        return UsageLimits(request_limit=scenario.max_model_calls or 50)


class PydanticAIHistory(_PydanticBase):
    surface = "history"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    async def setup_case(self, scenario, mode):
        self.runs: dict[int, list] = {}
        self.stream_events: dict[int, list] = {}

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        if mode == "stream":
            sink = self.stream_events.setdefault(run_index, [])
            async with agent.run_stream_events("go", usage_limits=self._limits(scenario)) as stream:
                async for ev in stream:
                    sink.append(ev)
            return "ok"
        with capture_run_messages() as messages:
            self.runs[run_index] = messages
            res = await agent.run("go", usage_limits=self._limits(scenario))
            return res.output

    async def collect(self):
        out: list[TraceEvent] = []
        order = 0
        for ri, messages in self.runs.items():
            by_id: dict[str, TraceEvent] = {}
            for m in messages:
                for p in m.parts:
                    if isinstance(p, ToolCallPart) and isinstance(m, ModelResponse):
                        order += 1
                        ev = TraceEvent(name=p.tool_name, args=parse_args(p.args), status="incomplete",
                                        call_id=p.tool_call_id, group=f"run{ri}", order=order)
                        out.append(ev)
                        by_id.setdefault(p.tool_call_id, ev)
                    elif isinstance(m, ModelRequest) and isinstance(p, (ToolReturnPart, RetryPromptPart)):
                        _apply_result(by_id.get(p.tool_call_id), p)
        for ri, events in self.stream_events.items():
            by_id = {}
            for e in events:
                if isinstance(e, FunctionToolCallEvent):
                    order += 1
                    p = e.part
                    ev = TraceEvent(name=p.tool_name, args=parse_args(p.args), status="incomplete",
                                    call_id=p.tool_call_id, group=f"run{ri}", order=order)
                    out.append(ev)
                    by_id.setdefault(p.tool_call_id, ev)
                elif isinstance(e, FunctionToolResultEvent):
                    p = getattr(e, "result", None) or getattr(e, "part", None)
                    _apply_result(by_id.get(getattr(p, "tool_call_id", None)), p)
        return out


def _apply_result(ev: TraceEvent | None, p) -> None:
    if ev is None or p is None:
        return
    if isinstance(p, ToolReturnPart):
        ev.status = "ok"
        ev.output = p.content
    else:
        ev.status = "error"
        ev.error = p.content if isinstance(p.content, str) else json.dumps(p.content, default=str)


class PydanticAIOtel(_PydanticBase):
    surface = "otel"
    capture = Capture(args=True, output=True, status=True, call_id=True)

    def _capabilities(self):
        tp, _ = otel_util.provider()
        return [Instrumentation(InstrumentationSettings(tracer_provider=tp, include_content=True))]

    async def setup_case(self, scenario, mode):
        otel_util.provider()[1].clear()

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        if mode == "stream":
            async with agent.run_stream_events("go", usage_limits=self._limits(scenario)) as stream:
                async for _ in stream:
                    pass
            return "ok"
        res = await agent.run("go", usage_limits=self._limits(scenario))
        return res.output

    async def collect(self):
        return collectors.collect("genai")
