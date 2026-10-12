"""End-to-end checks of the benchmark itself, using the reference adapter.

1. The reference loop is complete and faithful in every case, so a perfect
   score is achievable.
2. Mutation testing: each injected recording defect is caught by the
   scenario(s) designed for it, on the right axis.
3. The comparison, pytest helper and external-adapter loading work.
"""

import asyncio
import json
import subprocess
import sys

import pytest

from tracegap.adapters.reference import DEFECTS, ReferenceAdapter
from tracegap.compare import compare
from tracegap.harness import run_case
from tracegap.scenarios import MODES, SCENARIOS
from tracegap.testing import cases, check

BY_ID = {s.id: s for s in SCENARIOS}

# defect -> (scenario that must catch it, axis it must fail on)
EXPECTED = {
    "drop_rejected": ("S08", "complete"),
    "cancelled_as_ok": ("S17", "complete"),
    "drop_unfinished": ("S17", "complete"),
    "failed_as_ok": ("S05", "complete"),
    "shared_group": ("S21", "complete"),
    "split_group": ("S02", "complete"),
    "truncate_output": ("S13", "faithful"),
    "drop_error_detail": ("S05", "faithful"),
    "drop_nested": ("S22", "complete"),
    "double_record": ("S03", "complete"),
    "alter_args": ("S12", "faithful"),
}


@pytest.mark.parametrize("case", cases(ReferenceAdapter))
def test_reference_is_complete_and_faithful(case):
    r = check(case)
    assert r.executed + r.unexecuted > 0


def test_every_defect_has_an_expectation():
    assert set(EXPECTED) == set(DEFECTS)


@pytest.mark.parametrize("defect", sorted(EXPECTED))
@pytest.mark.parametrize("mode", MODES)
def test_injected_defect_is_detected(defect, mode):
    sid, axis = EXPECTED[defect]
    r = asyncio.run(run_case(ReferenceAdapter({defect}), BY_ID[sid], mode))
    assert getattr(r, axis) is False, f"{defect} not detected by {sid} ({axis})"
    if axis == "faithful":
        assert r.complete, f"{defect} should be a fidelity failure only"


def _results(passed_flags):
    return {"results": [
        {"adapter": "a", "scenario": f"S{i:02d}", "mode": "invoke", "complete": c, "faithful": True,
         "failures": [] if c else ["x"], "fidelity_failures": []}
        for i, c in enumerate(passed_flags)
    ]}


def test_compare_flags_regressions_and_improvements():
    d = compare(_results([True, False, True]), _results([False, True, True]))
    assert [k for k, axis, _ in d["regressions"]] == [("a", "S00", "invoke")]
    assert d["improvements"] == [(("a", "S01", "invoke"), "complete")]


def test_external_adapter_module_and_fail_on(tmp_path):
    out = tmp_path / "r.json"
    cmd = [sys.executable, "-m", "tracegap.cli", "--adapter-module", "tracegap.adapters.reference:ReferenceAdapter",
           "--scenarios", "S01", "S17", "--out", str(out), "--traces", "", "--fail-on", "any"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    data = json.loads(out.read_text())
    assert {r["adapter"] for r in data["results"]} == {"reference/minimal"}
    assert all(r["passed"] for r in data["results"])
