"""Runs scenarios against adapters and scores the recorded traces."""

from __future__ import annotations

import asyncio
import copy
import os
import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .core import Capture, GroundTruth, RunScript, Scenario, TraceEvent, Turn, active, set_active
from .scenarios import assign_call_ids

CASE_TIMEOUT = float(os.environ.get("TRACEGAP_CASE_TIMEOUT", "60"))


# --------------------------------------------------------------------------
# Script cursor shared by every adapter's scripted model
# --------------------------------------------------------------------------


class ScriptCursor:
    """Hands out scripted turns in order and logs emitted calls as ground
    truth. Adapters wrap this in their framework's model interface."""

    def __init__(self, script: RunScript, run_index: int, nested: bool = False):
        self.script = script
        self.run_index = run_index
        self.nested = nested
        self.i = 0

    async def next_turn(self) -> Turn:
        if self.i >= len(self.script.turns):
            return Turn(final="done")
        turn = self.script.turns[self.i]
        self.i += 1
        if turn.delay:
            await asyncio.sleep(turn.delay)
        if turn.raise_error:
            from .core import ModelProviderError

            raise ModelProviderError(turn.raise_error)
        for c in turn.calls:
            active().emit(self.run_index, c, nested=self.nested)
        return turn


# --------------------------------------------------------------------------
# Adapter interface
# --------------------------------------------------------------------------


class Adapter:
    framework: str = "?"
    surface: str = "?"
    capture: Capture = Capture(args=True, output=True, status=True, call_id=True)
    version: str = "?"

    @property
    def key(self) -> str:
        return f"{self.framework}/{self.surface}"

    async def setup_case(self, scenario: Scenario, mode: str) -> None:  # pragma: no cover
        raise NotImplementedError

    async def run(self, run_index: int, script: RunScript, scenario: Scenario, mode: str) -> Any:
        raise NotImplementedError

    async def collect(self) -> list[TraceEvent]:
        raise NotImplementedError

    async def drain(self) -> None:
        """Wait for any work the framework left running (for example worker
        threads of a synchronous framework) so it cannot leak into the next
        case. Called after scoring."""

    async def teardown_case(self) -> None:
        pass


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def _norm(v: Any) -> Any:
    try:
        return json.loads(json.dumps(v, sort_keys=True, default=str))
    except Exception:
        return repr(v)


def output_match(recorded: Any, actual: Any) -> str:
    """Return exact | truncated | mismatch | missing."""
    if recorded is None and actual is not None:
        return "missing"
    cands: list[str] = []
    if isinstance(actual, str):
        cands.append(actual)
        cands.append(json.dumps(actual))
    else:
        cands += [json.dumps(actual), json.dumps(actual, separators=(",", ":")), str(actual), repr(actual)]
        if actual is None:
            cands += ["", "null", "None"]
    if not isinstance(recorded, str):
        if _norm(recorded) == _norm(actual):
            return "exact"
        recorded_s = str(recorded)
    else:
        recorded_s = recorded
    if recorded_s in cands:
        return "exact"
    try:
        if _norm(json.loads(recorded_s)) == _norm(actual):
            return "exact"
    except Exception:
        pass
    try:
        import ast

        if _norm(ast.literal_eval(recorded_s)) == _norm(actual):
            return "exact"
    except Exception:
        pass
    stripped = recorded_s.rstrip(". …").removesuffix("[truncated]").rstrip()
    for c in cands:
        if len(stripped) >= 1 and len(stripped) < len(c) and c.startswith(stripped):
            return "truncated"
        if len(c) > 1000 and stripped[:1000] == c[:1000]:
            return "truncated"
    if recorded is None:
        return "missing"
    return "mismatch"


@dataclass
class CaseResult:
    adapter: str
    scenario: str
    category: str
    mode: str
    passed: bool
    run_outcome: str
    executed: int = 0
    executed_recorded: int = 0
    status_checked: int = 0
    status_correct: int = 0
    misreported_ok: int = 0
    args_checked: int = 0
    args_exact: int = 0
    output_checked: int = 0
    output_exact: int = 0
    output_truncated: int = 0
    unexecuted: int = 0
    unexecuted_visible: int = 0
    phantoms: int = 0
    duplicates: int = 0
    unattributed: int = 0
    isolation_violations: int = 0
    fragmented_runs: int = 0
    orphaned_tools: int = 0  # tools still running after the run ended (informational)
    complete: bool = False
    faithful: bool = False
    failures: list[str] = field(default_factory=list)
    fidelity_failures: list[str] = field(default_factory=list)
    error: Optional[str] = None
    seconds: float = 0.0
    trace: Optional[dict] = None  # ground truth + recorded events (written to the trace corpus)
    run_errors: list[str] = field(default_factory=list)  # exceptions raised by the runs, for debugging


def score(
    adapter: Adapter, scn: Scenario, mode: str, gt: GroundTruth, events: list[TraceEvent], run_outcome: str
) -> CaseResult:
    cap = adapter.capture
    r = CaseResult(adapter.key, scn.id, scn.category, mode, False, run_outcome)

    tag_run = {e.tag: e.run_index for e in gt.emissions}
    emitted_tags = [e.tag for e in gt.emissions]
    id_to_tags: dict[str, list[str]] = {}
    for e in gt.emissions:
        id_to_tags.setdefault(e.call_id, []).append(e.tag)

    # ---- attribute each recorded event to a tag ----
    by_tag: dict[str, list[TraceEvent]] = {}
    for ev in events:
        t = ev.tag
        if t is None and ev.call_id is not None:
            cands = id_to_tags.get(ev.call_id, [])
            if len(cands) == 1:
                t = cands[0]
            elif len(cands) > 1:
                # Ambiguous id (duplicate-id scenario): assign to the first
                # candidate not yet claimed, mirroring what a consumer would do.
                for c in cands:
                    if c not in by_tag:
                        t = c
                        break
                else:
                    t = cands[0]
        if t is None:
            r.unattributed += 1
            r.failures.append(f"unattributable trace event (name={ev.name!r}, call_id={ev.call_id!r})")
            continue
        if t not in tag_run:
            r.phantoms += 1
            r.failures.append(f"phantom: trace has call {t!r} the model never emitted")
            continue
        by_tag.setdefault(t, []).append(ev)

    # ---- executed calls ----
    led_by_tag: dict[str, list] = {}
    for le in gt.ledger:
        led_by_tag.setdefault(le.tag, []).append(le)

    for tag in dict.fromkeys(emitted_tags):
        les = led_by_tag.get(tag, [])
        evs = by_tag.get(tag, [])
        if les:
            for i, le in enumerate(les):
                r.executed += 1
                ev = evs[i] if i < len(evs) else None
                if ev is None:
                    r.failures.append(f"{tag}: executed ({le.status}) but missing from trace")
                    continue
                r.executed_recorded += 1
                if cap.status:
                    r.status_checked += 1
                    want_ok = le.status == "ok"
                    if want_ok and ev.status == "ok":
                        r.status_correct += 1
                    elif not want_ok and ev.status in ("error", "incomplete"):
                        r.status_correct += 1
                    else:
                        if not want_ok and ev.status == "ok":
                            r.misreported_ok += 1
                        r.failures.append(f"{tag}: actual={le.status} but trace status={ev.status}")
                if cap.args:
                    r.args_checked += 1
                    if _norm(ev.args) == _norm(le.args):
                        r.args_exact += 1
                    else:
                        r.fidelity_failures.append(f"{tag}: args differ: trace={_short(ev.args)} actual={_short(le.args)}")
                if cap.output:
                    if le.status == "ok":
                        r.output_checked += 1
                        m = output_match(ev.output, le.output)
                        if m == "exact":
                            r.output_exact += 1
                        else:
                            if m == "truncated":
                                r.output_truncated += 1
                            r.fidelity_failures.append(
                                f"{tag}: output {m}: trace={_short(ev.output)} actual={_short(le.output)}"
                            )
                    elif le.status == "error":
                        r.output_checked += 1
                        reason = (le.error or "").split(": ", 1)[-1]
                        blob = f"{ev.error or ''} {ev.output or ''}"
                        if reason and reason in blob:
                            r.output_exact += 1
                        else:
                            r.fidelity_failures.append(f"{tag}: error message not recorded (actual={le.error!r})")
            extra = len(evs) - len(les)
            if extra > 0:
                r.duplicates += extra
                r.failures.append(f"{tag}: recorded {len(evs)} times but executed {len(les)} time(s)")
        else:
            r.unexecuted += 1
            if not evs:
                r.failures.append(f"{tag}: emitted but never executed, and the attempt is invisible in the trace")
            else:
                ev = evs[0]
                if ev.status == "ok":
                    r.misreported_ok += 1
                    r.phantoms += 1
                    r.failures.append(f"{tag}: never executed but trace reports success")
                else:
                    r.unexecuted_visible += 1
                if len(evs) > 1:
                    r.duplicates += len(evs) - 1
                    r.failures.append(f"{tag}: never executed but recorded {len(evs)} times")

    # ---- isolation: a framework run group must hold one scenario run ----
    groups: dict[str, set] = {}
    for tag, evs in by_tag.items():
        for ev in evs:
            if ev.group is not None:
                groups.setdefault(ev.group, set()).add(tag_run[tag])
    # Fragmentation: one scenario run's calls spread over several trace groups
    # means the run cannot be reassembled from the trace.
    run_groups: dict[int, set] = {}
    for tag, evs in by_tag.items():
        for ev in evs:
            if ev.group is not None:
                run_groups.setdefault(tag_run[tag], set()).add(ev.group)
    for ri, gs in run_groups.items():
        if len(gs) > 1:
            r.fragmented_runs += 1
            r.failures.append(f"run {ri}: its calls are split across {len(gs)} unrelated trace groups")
    if len(scn.runs) > 1:
        for g, runs in groups.items():
            if len(runs) > 1:
                r.isolation_violations += 1
                r.failures.append(f"trace group {g!r} mixes calls from runs {sorted(runs)}")
        if events and all(ev.group is None for ev in events):
            r.failures.append("trace events carry no run identity; runs cannot be separated")
            r.isolation_violations += 1

    r.complete = not r.failures
    r.faithful = not r.fidelity_failures
    r.passed = r.complete and r.faithful
    return r


def _short(v: Any, n: int = 80) -> str:
    s = repr(v)
    return s if len(s) <= n else s[: n - 3] + "..." + f"(len={len(s)})"


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


async def run_case(adapter: Adapter, scenario: Scenario, mode: str) -> CaseResult:
    scn = copy.deepcopy(scenario)
    assign_call_ids(scn)
    gt = GroundTruth()
    set_active(gt)
    t0 = time.perf_counter()
    outcome = "completed"
    err = None
    try:
        await adapter.setup_case(scn, mode)
        tasks = [asyncio.create_task(adapter.run(i, rs, scn, mode)) for i, rs in enumerate(scn.runs)]
        if scn.cancel_after:
            loop = asyncio.get_running_loop()
            for t in tasks:
                loop.call_later(scn.cancel_after, t.cancel)
        done = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), CASE_TIMEOUT)
        outs = []
        run_errors = []
        for d in done:
            if isinstance(d, asyncio.CancelledError):
                outs.append("cancelled")
            elif isinstance(d, BaseException):
                outs.append(f"raised {type(d).__name__}")
                run_errors.append(f"{type(d).__name__}: {d}"[:500])
            else:
                outs.append("completed")
        outcome = ",".join(sorted(set(outs)))
        await asyncio.sleep(0.05)  # let background span exporters settle
        events = await adapter.collect()
        if not gt.emissions:
            # The scripted model never produced a call: the case did not
            # actually exercise anything. Never let that count as a pass.
            raise RuntimeError(f"invalid case: model emitted no tool calls (run outcome: {outcome}; "
                               f"{'; '.join(run_errors) or 'no exception'})")
        res = score(adapter, scn, mode, gt, events, outcome)
        res.trace = {
            "emissions": [asdict(e) for e in gt.emissions],
            "ledger": [asdict(le) for le in gt.ledger],
            "recorded": [{k: v for k, v in asdict(ev).items() if k != "raw"} for ev in events],
        }
        res.orphaned_tools = sum(1 for le in gt.ledger if le.status == "running")
        res.run_errors = run_errors
    except Exception as e:  # harness/adapter bug: record, don't hide
        err = "".join(traceback.format_exception_only(type(e), e)).strip()
        res = CaseResult(adapter.key, scn.id, scn.category, mode, False, "harness-error", error=err,
                         failures=[f"harness error: {err}"])
    finally:
        # Drain orphaned tools so they cannot leak spans into the next case.
        for _ in range(100):
            if not any(le.status == "running" for le in gt.ledger):
                break
            await asyncio.sleep(0.05)
        try:
            await asyncio.wait_for(adapter.drain(), 15)
        except Exception:
            pass
        try:
            await adapter.teardown_case()
        except Exception:
            pass
        set_active(None)
    res.seconds = round(time.perf_counter() - t0, 3)
    return res
