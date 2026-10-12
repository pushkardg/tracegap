import json
from pathlib import Path

from tracegap.generator import generate
from tracegap.scenarios import SCENARIOS
from tracegap.tiers import STABLE, STRESS, tier, tiers_for

ROOT = Path(__file__).resolve().parents[1]


def test_core_tiers():
    tiers = {s.id: tier(s) for s in SCENARIOS}
    assert [k for k, v in tiers.items() if v == STRESS] == ["S07"]
    assert tiers["S05"] == STABLE  # a single failing call is deterministic


def test_tier_is_structural_and_deterministic():
    a = [tier(s) for s in generate(200, 1)]
    b = [tier(s) for s in generate(200, 1)]
    assert a == b
    assert a.count(STRESS) == 118


def test_every_unstable_case_is_in_stress_tier():
    gen = json.loads((ROOT / "results/generated/results.json").read_text())
    tm = tiers_for(gen)
    unstable = json.loads((ROOT / "results/generated/unstable_cases.json").read_text())
    assert len(unstable) == 148
    for _adapter, scenario, _mode in unstable:
        assert tm[scenario] == STRESS


def test_tiers_for_core_results():
    core = json.loads((ROOT / "results/results.json").read_text())
    tm = tiers_for(core)
    assert set(tm) >= {r["scenario"] for r in core["results"]}
