"""Repro: OpenAI Agents SDK closes a cancelled tool's function span with no error.

When a run is cancelled while a function tool is executing, the tool's
FunctionSpan ends with ``span.error is None`` and ``output is None``. Trace
consumers (dashboards, exporters, audits) therefore see a successful call
that never finished.

Root cause: ``SpanImpl.__exit__`` (agents/tracing/spans.py) ignores
``exc_type``, and the tool executor's ``except Exception`` does not catch
``asyncio.CancelledError`` (a BaseException), so no error is attached.

Expected: the span records an error/cancelled status.
Run: python openai_agents_cancelled_tool_reported_ok.py
"""

import asyncio

from agents import Agent, Runner, function_tool, set_trace_processors
from agents.testing.model import ModelStep, ScriptedModel, assistant_message, function_call
from agents.tracing import TracingProcessor
from agents.tracing.span_data import FunctionSpanData

ended = []


class Recorder(TracingProcessor):
    def on_trace_start(self, t): ...
    def on_trace_end(self, t): ...
    def on_span_start(self, s): ...
    def on_span_end(self, s):
        if isinstance(s.span_data, FunctionSpanData):
            ended.append((s.span_data.name, s.error, s.span_data.output))
    def shutdown(self): ...
    def force_flush(self): ...


tool_finished = False


@function_tool
async def slow() -> str:
    """Takes two seconds."""
    global tool_finished
    await asyncio.sleep(2)
    tool_finished = True
    return "done"


async def main():
    set_trace_processors([Recorder()])
    model = ScriptedModel([
        ModelStep(output=[function_call("slow", {}, call_id="c1")]),
        ModelStep(output=[assistant_message("ok")]),
    ])
    agent = Agent(name="a", model=model, tools=[slow])
    task = asyncio.create_task(Runner.run(agent, "go"))
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.1)
    print("tool finished:", tool_finished)
    for name, error, output in ended:
        print(f"span {name!r}: error={error!r} output={output!r}")
    assert ended and ended[0][1] is None and not tool_finished
    print("BUG REPRODUCED: cancelled tool span has no error (indistinguishable from success)")


asyncio.run(main())
