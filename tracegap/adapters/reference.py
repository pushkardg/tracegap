"""Reference adapter: a deliberately minimal agent loop that records tool calls
correctly. It is not a framework; it exists to show that a complete and
faithful score on every TraceGap scenario is achievable, and to give framework
authors a concrete model of the bookkeeping involved:

* record the attempt before validating or executing the call;
* close the record on every exit path (success, exception, cancellation);
* never drop a requested call, even when it is rejected or a limit is hit;
* tag every record with the identity of the run that owns it.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import uuid
from typing import Any, get_type_hints

from ..core import Capture, TraceEvent
from ..harness import Adapter, ScriptCursor
from ..tools import TOOLS, make_delegate


# Injectable recording defects, used to check that the benchmark detects each
# kind of mistake (mutation testing). The reference loop uses none of them.
DEFECTS = {
    "drop_rejected": "rejected calls (unknown tool, bad arguments) are not recorded",
    "cancelled_as_ok": "a cancelled call is closed as a success",
    "drop_unfinished": "calls that never finish are removed from the record",
    "failed_as_ok": "a call that raised is recorded as a success",
    "shared_group": "every run is recorded under the same trace id",
    "split_group": "every call gets its own trace id",
    "truncate_output": "outputs are cut to 1,000 characters",
    "drop_error_detail": "error messages are not recorded",
    "drop_nested": "calls made inside a nested agent are not recorded",
    "double_record": "parallel calls are recorded twice",
    "alter_args": "arguments are re-serialized lossily (non-ASCII replaced)",
}


class _Recorder:
    def __init__(self, defects: frozenset = frozenset()) -> None:
        self.events: list[TraceEvent] = []
        self._order = itertools.count(1)
        self.defects = defects
        self.nested_depth = 0

    def open(self, name, args, call_id, group) -> TraceEvent:
        a = json.loads(json.dumps(args))
        if "alter_args" in self.defects:
            a = {k: (v.encode("ascii", "replace").decode() if isinstance(v, str) else v) for k, v in a.items()}
        if "split_group" in self.defects:
            group = f"{group}-{next(self._order)}"
        ev = TraceEvent(name=name, args=a, status="incomplete",
                        call_id=call_id, group=group, order=next(self._order))
        if not ("drop_nested" in self.defects and self.nested_depth > 0):
            self.events.append(ev)
        return ev

    def finalize(self) -> list[TraceEvent]:
        evs = list(self.events)
        if "drop_unfinished" in self.defects:
            evs = [e for e in evs if e.status != "incomplete" and e.error != "cancelled"]
        if "truncate_output" in self.defects:
            for e in evs:
                if isinstance(e.output, str) and len(e.output) > 1000:
                    e.output = e.output[:1000]
        return evs


def _validate(fn, args: dict) -> None:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    for name, p in sig.parameters.items():
        if name not in args and p.default is inspect.Parameter.empty:
            raise TypeError(f"missing required argument {name!r}")
    for name, v in args.items():
        if name not in sig.parameters:
            raise TypeError(f"unexpected argument {name!r}")
        t = hints.get(name)
        if t in (int, float) and (isinstance(v, bool) or not isinstance(v, (int, float))):
            raise TypeError(f"argument {name!r} must be {t.__name__}")
        if t is str and not isinstance(v, str):
            raise TypeError(f"argument {name!r} must be str")


async def _run_call(rec: _Recorder, tools: dict, call, group: str, parallel: bool = False) -> str:
    ev = rec.open(call.name, call.args, call.call_id, group)
    if parallel and "double_record" in rec.defects:
        rec.open(call.name, call.args, call.call_id, group).status = "ok"
    try:
        fn = tools.get(call.name)
        if fn is None:
            raise LookupError(f"unknown tool {call.name!r}")
        try:
            _validate(fn, call.args)
        except TypeError:
            if "drop_rejected" in rec.defects and ev in rec.events:
                rec.events.remove(ev)
            raise
        result = fn(**call.args)
        if inspect.isawaitable(result):
            result = await result
        ev.status, ev.output = "ok", result
        return json.dumps(result, default=str) if not isinstance(result, str) else result
    except asyncio.CancelledError:
        ev.status, ev.error = ("ok", None) if "cancelled_as_ok" in rec.defects else ("error", "cancelled")
        raise
    except LookupError as e:
        if "drop_rejected" in rec.defects and ev in rec.events:
            rec.events.remove(ev)
        ev.status, ev.error = "error", f"{type(e).__name__}: {e}"
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001 - recorded, then reported to the model
        if "failed_as_ok" in rec.defects:
            ev.status = "ok"
        else:
            ev.status = "error"
            ev.error = "error" if "drop_error_detail" in rec.defects else f"{type(e).__name__}: {e}"
        return f"error: {e}"


async def _loop(rec: _Recorder, cursor: ScriptCursor, tools: dict, group: str, max_calls: int) -> str:
    for _ in range(max_calls):
        turn = await cursor.next_turn()
        if not turn.calls:
            return turn.final or "done"
        # Tools in one turn run concurrently; one failure never cancels siblings.
        par = len(turn.calls) > 1
        await asyncio.gather(*[_run_call(rec, tools, c, group, par) for c in turn.calls])
    return "stopped: model-call limit reached"


class ReferenceAdapter(Adapter):
    framework = "reference"
    surface = "minimal"
    capture = Capture(args=True, output=True, status=True, call_id=True)
    version = "tracegap reference loop"

    def __init__(self, defects: frozenset | set = frozenset()) -> None:
        unknown = set(defects) - set(DEFECTS)
        if unknown:
            raise ValueError(f"unknown defects: {sorted(unknown)}")
        self.defects = frozenset(defects)
        if self.defects:
            self.surface = "minimal+" + "+".join(sorted(self.defects))

    async def setup_case(self, scenario, mode):
        self.rec = _Recorder(self.defects)

    def _tools(self, scenario, nested_script, run_index, group):
        tools = {}
        for name in scenario.tools:
            if name == "delegate":
                async def run_inner(script=nested_script, ri=run_index):
                    self.rec.nested_depth += 1
                    try:
                        return await _loop(self.rec, ScriptCursor(script, ri, nested=True),
                                           self._tools(scenario, None, ri, group), group, 50)
                    finally:
                        self.rec.nested_depth -= 1

                tools["delegate"] = make_delegate(run_inner)
            else:
                tools[name] = TOOLS[name]
        return tools

    async def run(self, run_index, script, scenario, mode):
        group = "shared" if "shared_group" in self.defects else f"run-{uuid.uuid4().hex[:8]}"
        tools = self._tools(scenario, script.nested, run_index, group)
        return await _loop(self.rec, ScriptCursor(script, run_index), tools, group, scenario.max_model_calls or 50)

    async def collect(self):
        return self.rec.finalize()
