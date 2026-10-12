"""A complete TraceGap adapter for a tiny made-up framework, in one file.

Copy this file when adding a real framework. The top half (ToyAgent) stands
in for the framework you are testing; in a real adapter you import it
instead. The bottom half (ToyHooksAdapter) is what you write.

Check it:

    python -m tracegap.check_adapter examples.toy_adapter:ToyHooksAdapter

An adapter does three things, and nothing else:

1. Drive the framework with a *scripted model*: wrap ``ScriptCursor`` in the
   framework's model interface so every model turn comes from the scenario.
2. Give the agent the scenario's tools from ``tracegap.tools.TOOLS`` (they
   write the ground-truth ledger themselves).
3. Read what the framework recorded, **only through its public
   observability surface** (callbacks, events, spans, message history), and
   return it as ``TraceEvent`` objects. Never rebuild events from the ledger
   and never patch framework internals: the point is to score the surface.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable

from tracegap.core import Capture, TraceEvent
from tracegap.harness import Adapter, ScriptCursor
from tracegap.tools import TOOLS, make_delegate

# ---------------------------------------------------------------- the "framework"


class ToyAgent:
    """A minimal agent framework with a hooks-based observability surface:
    ``on_tool_start(run_id, call_id, name, args)`` and
    ``on_tool_end(run_id, call_id, output=None, error=None)``."""

    def __init__(self, model: Callable, tools: dict[str, Callable], hooks: Any = None, max_turns: int = 12):
        self.model, self.tools, self.hooks, self.max_turns = model, tools, hooks, max_turns

    async def _call(self, run_id, call):
        if self.hooks:
            self.hooks.on_tool_start(run_id, call["id"], call["name"], call["args"])
        try:
            fn = self.tools[call["name"]]
            out = await fn(**call["args"])
        except asyncio.CancelledError:
            if self.hooks:
                self.hooks.on_tool_end(run_id, call["id"], error="cancelled")
            raise
        except Exception as e:  # noqa: BLE001 - reported to the model
            if self.hooks:
                self.hooks.on_tool_end(run_id, call["id"], error=f"{type(e).__name__}: {e}")
            return f"error: {e}"
        if self.hooks:
            self.hooks.on_tool_end(run_id, call["id"], output=out)
        return out

    async def run(self, prompt: str, stream: bool = False):
        run_id = uuid.uuid4().hex
        for _ in range(self.max_turns):
            reply = await self.model(prompt)
            if not reply["tool_calls"]:
                return reply["text"]
            await asyncio.gather(*[self._call(run_id, c) for c in reply["tool_calls"]])
        return "turn limit"


# ---------------------------------------------------------------- the adapter


class _Hooks:
    """Collects what the framework's hooks report, as TraceEvents."""

    def __init__(self) -> None:
        self.events: dict[tuple[str, str], TraceEvent] = {}
        self.order = 0

    def on_tool_start(self, run_id, call_id, name, args):
        self.order += 1
        self.events[(run_id, call_id)] = TraceEvent(
            name=name, args=dict(args), status="incomplete",  # until the end hook says otherwise
            call_id=call_id, group=run_id, order=self.order)

    def on_tool_end(self, run_id, call_id, output=None, error=None):
        ev = self.events.get((run_id, call_id))
        if ev is None:
            return
        if error is None:
            ev.status, ev.output = "ok", output
        else:
            ev.status, ev.error = "error", error


class ToyHooksAdapter(Adapter):
    framework = "toy"
    surface = "hooks"
    # Say honestly what the surface records; fields set to False are not scored.
    capture = Capture(args=True, output=True, status=True, call_id=True)
    version = "toy 1.0"  # real adapters: f"myframework {importlib.metadata.version('myframework')}"

    async def setup_case(self, scenario, mode):
        self.hooks = _Hooks()

    def _model(self, cursor: ScriptCursor):
        """Wrap the scripted cursor in the framework's model interface."""

        async def model(prompt):
            turn = await cursor.next_turn()
            calls = [{"id": c.call_id, "name": c.name, "args": dict(c.args)} for c in turn.calls]
            return {"tool_calls": calls, "text": turn.final or "done"}

        return model

    def _agent(self, cursor, scenario, nested_script, run_index):
        tools = {}
        for name in scenario.tools:
            if name == "delegate":  # S22: a tool that runs a nested agent
                async def run_inner(script=nested_script, ri=run_index):
                    inner = self._agent(ScriptCursor(script, ri, nested=True), scenario, None, ri)
                    return await inner.run("sub-task")

                tools["delegate"] = make_delegate(run_inner)
            else:
                tools[name] = TOOLS[name]
        return ToyAgent(self._model(cursor), tools, hooks=self.hooks,
                        max_turns=scenario.max_model_calls or 12)

    async def run(self, run_index, script, scenario, mode):
        agent = self._agent(ScriptCursor(script, run_index), scenario, script.nested, run_index)
        return await agent.run("go", stream=(mode == "stream"))

    async def collect(self):
        return sorted(self.hooks.events.values(), key=lambda e: e.order)
