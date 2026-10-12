"""Negative controls for the scorer: a perfect trace must pass, and each
injected defect must be caught by the right check."""

import copy

import pytest

from tracegap.core import Call, Capture, GroundTruth, RunScript, Scenario, TraceEvent, Turn
from tracegap.harness import Adapter, output_match, score


class FakeAdapter(Adapter):
    framework, surface = "fake", "test"

    def __init__(self, capture=None):
        self.capture = capture or Capture(args=True, output=True, status=True, call_id=True)


def scenario(nruns=1):
    runs = [RunScript([Turn(calls=[Call("echo", {"tag": f"r{i}a", "text": "x"})])]) for i in range(nruns)]
    return Scenario("X", "test", "t", "d", runs, tools=["echo"])


def truth(statuses=("ok", "ok"), nruns=1):
    """Two calls per run: tags r{i}a, r{i}b."""
    gt = GroundTruth()
    for ri in range(nruns):
        for j, st in zip("ab", statuses):
            tag = f"r{ri}{j}"
            c = Call("echo", {"tag": tag, "text": "x"}, call_id=f"id_{tag}")
            gt.emit(ri, c)
            if st == "never":
                continue
            le = gt.start("echo", c.args)
            le.status = st
            le.output = "echo:x" if st == "ok" else None
            le.error = "ToolFailure: tool failed: boom" if st == "error" else None
    return gt


def perfect(gt, group_by_run=True):
    evs = []
    for le in gt.ledger:
        run = int(le.tag[1])
        evs.append(TraceEvent(name=le.name, args=dict(le.args),
                              status="ok" if le.status == "ok" else "error",
                              output=le.output, error=le.error, call_id=f"id_{le.tag}",
                              group=f"g{run}" if group_by_run else "g"))
    for em in gt.emissions:
        if not any(le.tag == em.tag for le in gt.ledger):
            evs.append(TraceEvent(name=em.name, args=dict(em.args), status="error", call_id=em.call_id,
                                  group=f"g{em.run_index}"))
    return evs


def run(evs, gt, nruns=1, capture=None):
    return score(FakeAdapter(capture), scenario(nruns), "invoke", gt, evs, "completed")


def test_perfect_trace_passes():
    gt = truth(("ok", "error"))
    r = run(perfect(gt), gt)
    assert r.passed, r.failures + r.fidelity_failures


def test_missing_call_detected():
    gt = truth()
    r = run(perfect(gt)[:1], gt)
    assert not r.complete and r.executed_recorded == 1


def test_cancelled_reported_ok_detected():
    gt = truth(("ok", "cancelled"))
    evs = perfect(gt)
    evs[1].status = "ok"
    r = run(evs, gt)
    assert not r.complete and r.misreported_ok == 1


def test_incomplete_counts_as_honest_for_cancelled():
    gt = truth(("ok", "cancelled"))
    evs = perfect(gt)
    evs[1].status = "incomplete"
    assert run(evs, gt).complete


def test_invisible_attempt_detected():
    gt = truth(("ok", "never"))
    evs = perfect(gt)[:1]
    r = run(evs, gt)
    assert not r.complete and r.unexecuted == 1 and r.unexecuted_visible == 0


def test_never_executed_reported_ok_is_phantom():
    gt = truth(("ok", "never"))
    evs = perfect(gt)
    evs[1].status = "ok"
    r = run(evs, gt)
    assert not r.complete and r.phantoms == 1


def test_unknown_tag_is_phantom():
    gt = truth()
    evs = perfect(gt) + [TraceEvent(name="echo", args={"tag": "zzz"}, status="ok", group="g0")]
    r = run(evs, gt)
    assert not r.complete and r.phantoms == 1


def test_duplicate_detected():
    gt = truth()
    evs = perfect(gt)
    evs.append(copy.deepcopy(evs[0]))
    r = run(evs, gt)
    assert not r.complete and r.duplicates == 1


def test_args_mismatch_is_fidelity_not_completeness():
    gt = truth()
    evs = perfect(gt)
    evs[0].args = {"tag": "r0a", "text": "changed"}
    r = run(evs, gt)
    assert r.complete and not r.faithful


def test_truncated_output_detected():
    assert output_match("abc...", "abcdefgh") == "truncated"
    assert output_match("abcdefgh", "abcdefgh") == "exact"
    assert output_match('{"a": 1}', {"a": 1}) == "exact"
    assert output_match("other", "abcdefgh") == "mismatch"
    assert output_match(None, "abc") == "missing"


def test_redacted_error_is_fidelity_failure():
    gt = truth(("error", "ok"))
    evs = perfect(gt)
    evs[0].error = "Error details are redacted."
    r = run(evs, gt)
    assert r.complete and not r.faithful


def test_isolation_violation_detected():
    gt = truth(nruns=2)
    r = run(perfect(gt, group_by_run=False), gt, nruns=2)
    assert not r.complete and r.isolation_violations == 1


def test_fragmentation_detected():
    gt = truth()
    evs = perfect(gt)
    evs[1].group = "other-trace"
    r = run(evs, gt)
    assert not r.complete and r.fragmented_runs == 1


def test_call_id_matching_without_args():
    gt = truth()
    evs = perfect(gt)
    for e in evs:
        e.args = None
        e.output = None
    cap = Capture(args=False, output=False, status=True, call_id=True)
    assert run(evs, gt, capture=cap).passed


def test_empty_trace_fails():
    gt = truth()
    r = run([], gt)
    assert not r.complete
