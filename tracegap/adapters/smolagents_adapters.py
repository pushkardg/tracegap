"""smolagents (ToolCallingAgent), scored through two surfaces.

* ``memory``: ``agent.memory.steps`` (ActionStep.tool_calls), the record
  smolagents keeps of what the agent did. Per-call status and output are not
  recorded there (a step has one error and one joined observation string), so
  only presence, arguments and call ids are scored.
* ``openinference``: TOOL spans from ``openinference-instrumentation-smolagents``.

smolagents is synchronous: runs execute in a worker thread, and cancelling the
caller cannot stop that thread. smolagents ends a run by calling its own
``final_answer`` tool; that framework-internal call is excluded.
"""

from __future__ import annotations

import asyncio
import inspect
import typing
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version as _v

from smolagents import ChatMessage, Model, Tool, ToolCallingAgent
from smolagents.models import ChatMessageToolCall, MessageRole

try:
    from smolagents.models import ChatMessageToolCallFunction
except ImportError:  # smolagents <= 1.18
    from smolagents.models import ChatMessageToolCallDefinition as ChatMessageToolCallFunction

from .. import collectors, otel_util
from ..core import Capture, TraceEvent, parse_args
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate

_TYPES = {str: "string", int: "integer", float: "number"}
_FINAL = "final_answer"


def _run_sync(coro):
    """Run a coroutine from synchronous tool code, whether or not this thread
    already has a running event loop (nested agents run inside one)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _wrap(fn) -> Tool:
    hints = typing.get_type_hints(fn)
    params = list(inspect.signature(fn).parameters)

    class FnTool(Tool):
        name = fn.__name__
        description = (fn.__doc__ or fn.__name__).strip()
        inputs = {p: {"type": _TYPES.get(hints.get(p), "any"), "description": p} for p in params}
        output_type = "any"
        skip_forward_signature_validation = True

        def forward(self, **kw):
            r = fn(**kw)
            return _run_sync(r) if inspect.isawaitable(r) else r

    FnTool.__name__ = f"{fn.__name__}_tool"
    return FnTool()


class ScriptedModel(Model):
    def __init__(self, cursor: ScriptCursor, loop: asyncio.AbstractEventLoop):
        super().__init__(model_id="tracegap-scripted")
        self.cursor = cursor
        self.loop = loop

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kw):
        if not tools_to_call_from:
            # The framework is asking for a plain-text answer (for example after
            # max_steps). A real model offered no tools cannot call one, so answer
            # in text without consuming the script.
            return ChatMessage(role=MessageRole.ASSISTANT, content="done")
        # The cursor is async (delays, provider errors); run it on the harness loop.
        turn = asyncio.run_coroutine_threadsafe(self.cursor.next_turn(), self.loop).result()
        if turn.calls:
            calls = [(c.name, dict(c.args), c.call_id) for c in turn.calls]
        else:
            calls = [(_FINAL, {"answer": turn.final or "done"}, "final")]
        return ChatMessage(
            role=MessageRole.ASSISTANT, content="",
            tool_calls=[ChatMessageToolCall(function=ChatMessageToolCallFunction(name=n, arguments=a), id=i, type="function")
                        for n, a, i in calls],
        )


class _SmolBase(Adapter):
    framework = "smolagents"
    version = f"smolagents {_v('smolagents')}"

    async def setup_case(self, scenario, mode):
        self.agents: dict[int, ToolCallingAgent] = {}
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.futures = []

    def _agent(self, cursor, scenario, nested_script, run_index, loop):
        tools = []
        for name in scenario.tools:
            if name == "delegate":
                def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri, loop)
                    self.nested_agents.append((ri, inner))
                    return inner.run("sub-task")

                async def run_inner_async():
                    return run_inner()

                tools.append(_wrap(make_delegate(run_inner_async)))
            else:
                tools.append(_wrap(TOOLS[name]))
        return ToolCallingAgent(tools=tools, model=ScriptedModel(cursor, loop),
                                max_steps=scenario.max_model_calls or 50, verbosity_level=0)

    async def run(self, run_index, script, scenario, mode):
        loop = asyncio.get_running_loop()
        self.nested_agents = getattr(self, "nested_agents", [])
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index, loop)
        self.agents[run_index] = agent

        def work():
            if mode == "stream":
                for _ in agent.run("go", stream=True):
                    pass
                return "ok"
            return agent.run("go")

        fut = loop.run_in_executor(self.pool, work)
        self.futures.append(fut)
        return await fut

    async def drain(self):
        if self.futures:
            await asyncio.gather(*self.futures, return_exceptions=True)
        # Never block the event loop here: worker threads may still be waiting on
        # coroutines (the scripted model) scheduled on it.
        await asyncio.to_thread(self.pool.shutdown, True)


class SmolagentsMemory(_SmolBase):
    surface = "memory"
    capture = Capture(args=True, output=False, status=False, call_id=True)

    async def setup_case(self, scenario, mode):
        await super().setup_case(scenario, mode)
        self.nested_agents = []

    async def collect(self):
        out: list[TraceEvent] = []
        sources = list(self.agents.items()) + list(self.nested_agents)
        for ri, agent in sources:
            for step in list(agent.memory.steps):
                for tc in getattr(step, "tool_calls", None) or []:
                    if tc.name == _FINAL:
                        continue
                    out.append(TraceEvent(name=tc.name, args=parse_args(tc.arguments), status="unknown",
                                          call_id=tc.id, group=f"run{ri}", order=len(out)))
        return out


class SmolagentsOpenInference(_SmolBase):
    surface = "openinference"
    capture = Capture(args=True, output=True, status=True, call_id=False)
    _instrumented = False

    async def setup_case(self, scenario, mode):
        await super().setup_case(scenario, mode)
        tp, exp = otel_util.provider()
        if not SmolagentsOpenInference._instrumented:
            from openinference.instrumentation.smolagents import SmolagentsInstrumentor

            SmolagentsInstrumentor().instrument(tracer_provider=tp)
            SmolagentsOpenInference._instrumented = True
        exp.clear()
        self.nested_agents = []

    async def collect(self):
        return [e for e in collectors.collect("openinference") if e.name != _FINAL]
