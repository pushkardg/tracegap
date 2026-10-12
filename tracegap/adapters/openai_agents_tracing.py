"""OpenAI Agents SDK scored through its tracing processor interface.

A custom ``TracingProcessor`` receives the same function spans the SDK's
default exporter (and third-party integrations) receive. The default
exporter is replaced so nothing leaves the machine.
"""

from __future__ import annotations

import json
from importlib.metadata import version as _v

from agents import Agent, RunConfig, Runner, function_tool, set_trace_processors
try:
    from agents.testing.model import ModelStep, ScriptedModel, assistant_message, function_call

    HAVE_TESTING = True
except ImportError:  # openai-agents < 0.21 has no agents.testing; use a minimal Model
    HAVE_TESTING = False
from agents.tracing import TracingProcessor
from agents.tracing.span_data import FunctionSpanData

from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate


def scripted_model(cursor: ScriptCursor, n_turns: int):
    if not HAVE_TESTING:
        return _LegacyScriptedModel(cursor)

    async def respond(call):
        turn = await cursor.next_turn()
        if turn.calls:
            return [function_call(c.name, dict(c.args), call_id=c.call_id) for c in turn.calls]
        return [assistant_message(turn.final or "done")]

    return ScriptedModel([ModelStep.respond(respond) for _ in range(n_turns + 5)])


def _legacy_output(turn):
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

    if turn.calls:
        return [ResponseFunctionToolCall(id=c.call_id, call_id=c.call_id, type="function_call", name=c.name,
                                         arguments=json.dumps(c.args), status="completed") for c in turn.calls]
    return [ResponseOutputMessage(id="msg", type="message", role="assistant", status="completed",
                                  content=[ResponseOutputText(text=turn.final or "done", type="output_text",
                                                              annotations=[])])]


from agents.models.interface import Model as _AgentsModel  # noqa: E402


class _LegacyScriptedModel(_AgentsModel):
    """Minimal agents Model for SDK versions without agents.testing."""

    def __init__(self, cursor: ScriptCursor):
        self.cursor = cursor

    async def get_response(self, *args, **kwargs):
        from agents.items import ModelResponse
        from agents.usage import Usage

        turn = await self.cursor.next_turn()
        return ModelResponse(output=_legacy_output(turn), usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        from openai.types.responses import Response, ResponseCompletedEvent

        turn = await self.cursor.next_turn()
        resp = Response.model_construct(id="resp", object="response", created_at=0, model="tracegap-scripted",
                                        output=_legacy_output(turn), parallel_tool_calls=True, tool_choice="auto",
                                        tools=[], usage=None, status="completed")
        yield ResponseCompletedEvent.model_construct(type="response.completed", response=resp, sequence_number=0)


class SpanRecorder(TracingProcessor):
    def __init__(self) -> None:
        self.events: dict[str, TraceEvent] = {}
        self.order = 0

    def on_trace_start(self, trace):
        pass

    def on_trace_end(self, trace):
        pass

    def on_span_start(self, span):
        if isinstance(span.span_data, FunctionSpanData):
            self.order += 1
            d = span.span_data
            self.events[span.span_id] = TraceEvent(
                name=d.name, args=parse_args(d.input), status="incomplete",
                group=span.trace_id, order=self.order,
            )

    def on_span_end(self, span):
        if not isinstance(span.span_data, FunctionSpanData):
            return
        d = span.span_data
        ev = self.events.get(span.span_id)
        if ev is None:
            self.order += 1
            ev = self.events[span.span_id] = TraceEvent(name=d.name, args=None, status="incomplete",
                                                        group=span.trace_id, order=self.order)
        ev.args = parse_args(d.input)
        ev.output = d.output
        if span.error:
            ev.status = "error"
            ev.error = json.dumps(span.error, default=str)
        else:
            ev.status = "ok"

    def shutdown(self):
        pass

    def force_flush(self):
        pass


class OpenAIAgentsTracing(Adapter):
    framework = "openai-agents"
    surface = "tracing"
    # Function spans carry name, input JSON, output and error, but no call id.
    capture = Capture(args=True, output=True, status=True, call_id=False)
    version = f"openai-agents {_v('openai-agents')}"

    async def setup_case(self, scenario, mode):
        self.rec = SpanRecorder()
        set_trace_processors([self.rec])

    def _agent(self, cursor, scenario, nested_script, run_index, n_turns):
        tools = []
        for name in scenario.tools:
            if name == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    c = ScriptCursor(script, ri, nested=True)
                    inner = self._agent(c, scenario, None, ri, len(script.turns))
                    res = await Runner.run(inner, "sub-task")
                    return res.final_output

                tools.append(function_tool(make_delegate(run_inner)))
            else:
                tools.append(function_tool(TOOLS[name]))
        return Agent(name=f"agent{run_index}", instructions="test",
                     model=scripted_model(cursor, n_turns), tools=tools)

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index, len(script.turns))
        max_turns = scenario.max_model_calls or 10
        cfg = RunConfig(trace_include_sensitive_data=True)
        if mode == "stream":
            res = Runner.run_streamed(agent, "go", max_turns=max_turns, run_config=cfg)
            async for _ in res.stream_events():
                pass
            return res.final_output
        res = await Runner.run(agent, "go", max_turns=max_turns, run_config=cfg)
        return res.final_output

    async def collect(self):
        return sorted(self.rec.events.values(), key=lambda e: e.order)

    async def teardown_case(self):
        set_trace_processors([])
