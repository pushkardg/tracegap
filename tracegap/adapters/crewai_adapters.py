"""CrewAI (Agent + Task + Crew with native function calling), scored through
its event bus: ToolUsageStarted / ToolUsageFinished / ToolUsageError events,
the documented way to observe what a crew does (``crewai_event_bus.on``).

Events are attributed to runs by ``task_id``: every run builds its own Task,
and a nested crew's task is mapped to the run that started it. That uses
knowledge the application has, so the run-isolation and fragmentation checks
are lenient for this surface.

CrewAI executes crews synchronously (``kickoff_async`` runs ``kickoff`` in a
worker thread), so cancelling the caller cannot stop a running crew.
Modes: ``invoke`` uses ``Crew.kickoff_async``; ``stream`` uses
``Crew(stream=True)`` and consumes the streamed chunks.
"""

from __future__ import annotations

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")

import asyncio  # noqa: E402
import inspect  # noqa: E402
import json  # noqa: E402
import typing  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from importlib.metadata import version as _v  # noqa: E402

from crewai import Agent, BaseLLM, Crew, Task  # noqa: E402
from crewai.events import (  # noqa: E402
    crewai_event_bus,
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)
from crewai.tools import BaseTool  # noqa: E402
from pydantic import BaseModel, create_model  # noqa: E402

from ..core import Capture, TraceEvent, parse_args  # noqa: E402
from ..harness import Adapter, ScriptCursor  # noqa: E402
from ..tools import TOOLS, make_delegate  # noqa: E402


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _tool(fn, name: str) -> BaseTool:
    hints = typing.get_type_hints(fn)
    fields = {p: (hints.get(p, typing.Any), ...) for p in inspect.signature(fn).parameters}
    Args = create_model(f"{name}_args", **fields)

    class FnTool(BaseTool):
        def _run(self, **kw):
            r = fn(**kw)
            return _run_sync(r) if inspect.isawaitable(r) else r

    return FnTool(name=name, description=(fn.__doc__ or name).strip(), args_schema=Args)


# Older CrewAI versions copy the LLM object and drop custom fields, so the
# script is looked up by model name instead of stored on the instance.
_SCRIPTS: dict[str, tuple] = {}


class ScriptedLLM(BaseLLM):
    @property
    def cursor(self):
        return _SCRIPTS[self.model][0]

    @property
    def loop(self):
        return _SCRIPTS[self.model][1]

    def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None,
             from_agent=None, response_model=None, **kw):
        if not tools:
            # CrewAI asks for a tool-less final answer (for example after
            # max_iter); a real model offered no tools cannot call one.
            return "done"
        turn = asyncio.run_coroutine_threadsafe(self.cursor.next_turn(), self.loop).result()
        if not turn.calls:
            return turn.final or "done"
        return [{"id": c.call_id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.args)}} for c in turn.calls]

    async def acall(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None,
                    from_agent=None, response_model=None, **kw):
        if not tools:
            return "done"
        turn = await self.cursor.next_turn()
        if not turn.calls:
            return turn.final or "done"
        return [{"id": c.call_id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.args)}} for c in turn.calls]

    def supports_function_calling(self) -> bool:
        return True

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 128_000


class _Bus:
    """One process-wide subscription; events are routed to the active adapter."""

    sink = None
    installed = False

    @classmethod
    def install(cls):
        if cls.installed:
            return
        cls.installed = True
        for E in (ToolUsageStartedEvent, ToolUsageFinishedEvent, ToolUsageErrorEvent):
            @crewai_event_bus.on(E)
            def _h(*args, E=E):
                ev = next((a for a in args if isinstance(a, E)), None)
                if ev is not None and cls.sink is not None:
                    cls.sink(ev)


class CrewAIEvents(Adapter):
    framework = "crewai"
    surface = "events"
    # Events carry name, args, output, error; no tool-call id.
    capture = Capture(args=True, output=True, status=True, call_id=False)
    version = f"crewai {_v('crewai')}"

    async def setup_case(self, scenario, mode):
        _Bus.install()
        self.raw: list = []
        _Bus.sink = self.raw.append
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.futures = []
        self.task_run: dict[str, int] = {}

    def _llm(self, cursor, loop) -> ScriptedLLM:
        key = f"tracegap-scripted-{id(cursor)}"
        _SCRIPTS[key] = (cursor, loop)
        return ScriptedLLM(model=key)

    def _crew(self, cursor, scenario, nested_script, run_index, mode, loop, name="agent"):
        tools = []
        for t in scenario.tools:
            if t == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._crew(ScriptCursor(script, ri, nested=True), scenario, None, ri, mode, loop, "inner")
                    return str(await inner.kickoff_async())

                tools.append(_tool(make_delegate(run_inner), "delegate"))
            else:
                tools.append(_tool(TOOLS[t], t))
        agent = Agent(role=f"{name}{run_index}", goal="test", backstory="test",
                      llm=self._llm(cursor, loop), tools=tools,
                      verbose=False, max_iter=scenario.max_model_calls or 50, allow_delegation=False)
        task = Task(description="go", expected_output="done", agent=agent)
        self.task_run[str(task.id)] = run_index
        return Crew(agents=[agent], tasks=[task], verbose=False, stream=(mode == "stream" and name != "inner"))

    async def run(self, run_index, script, scenario, mode):
        loop = asyncio.get_running_loop()
        crew = self._crew(ScriptCursor(script, run_index), scenario, script.nested, run_index, mode, loop)

        def work():
            out = crew.kickoff()
            if mode == "stream":
                for _ in out:
                    pass
                return str(getattr(out, "result", "ok"))
            return str(out)

        fut = loop.run_in_executor(self.pool, work)
        self.futures.append(fut)
        return await fut

    async def collect(self):
        if hasattr(crewai_event_bus, "flush"):
            await asyncio.to_thread(crewai_event_bus.flush, 10)
        else:  # CrewAI <= 1.8 has no flush(); give the handler pool time to drain.
            await asyncio.sleep(1.0)
        out: list[TraceEvent] = []
        by_event_id: dict[str, TraceEvent] = {}
        open_by_tag: dict = {}
        # Handlers run on a thread pool, so arrival order is not emission order.
        # Restore it, and link each finish/error to its start event by id.
        raw = sorted(self.raw, key=lambda e: (e.emission_sequence is None, e.emission_sequence or 0, e.timestamp))
        for ev in raw:
            args = parse_args(ev.tool_args)
            run = self.task_run.get(str(ev.task_id))
            group = f"task:{ev.task_id}" if run is None else f"run{run}"
            tag = args.get("tag") if isinstance(args, dict) else None
            if isinstance(ev, ToolUsageStartedEvent):
                te = TraceEvent(name=ev.tool_name, args=args, status="incomplete", group=group, order=len(out))
                out.append(te)
                by_event_id[ev.event_id] = te
                open_by_tag.setdefault(tag, []).append(te)
                continue
            te = by_event_id.get(ev.started_event_id) if ev.started_event_id else None
            if te is None:
                pending = [e for e in open_by_tag.get(tag, []) if e.status == "incomplete"]
                te = pending[0] if pending else None
            if te is None:
                te = TraceEvent(name=ev.tool_name, args=args, status="incomplete", group=group, order=len(out))
                out.append(te)
            if isinstance(ev, ToolUsageErrorEvent):
                te.status, te.error = "error", str(ev.error)
            else:
                failure = getattr(ev, "failure", None)
                if failure is not None:
                    te.status, te.error = "error", str(failure)
                else:
                    te.status, te.output = "ok", ev.output
        return out

    async def drain(self):
        if self.futures:
            await asyncio.gather(*self.futures, return_exceptions=True)
        await asyncio.to_thread(self.pool.shutdown, True)

    async def teardown_case(self):
        _Bus.sink = None
        _SCRIPTS.clear()
