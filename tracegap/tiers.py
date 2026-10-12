"""Stable and Stress tiers.

A scenario is in the **Stress** tier when any model turn (in any run, nested
runs included) emits two or more tool calls and at least one of them is a
tool that raises. How frameworks handle the siblings of a call that raises
is often a race: whether a sibling has started, finished, or had its result
recorded when the run aborts can depend on scheduling. All 148 verdicts that
differed between three full runs of the generated suite fall in this tier.

Every other scenario is in the **Stable** tier. Stable verdicts were
identical across repeated full runs (core: four runs; generated: three), so
the primary leaderboard and CI regression checks use only Stable cases.

The rule depends only on a scenario's structure, so the tier of any
generated scenario (any n, any seed) is known before it runs.
"""

from __future__ import annotations

import re

from .core import RunScript, Scenario

STABLE, STRESS = "stable", "stress"
RAISING_TOOLS = {"fail"}


def tier(scenario: Scenario) -> str:
    def walk(rs: RunScript) -> bool:
        for t in rs.turns:
            if len(t.calls) > 1 and any(c.name in RAISING_TOOLS for c in t.calls):
                return True
        return bool(rs.nested and walk(rs.nested))

    return STRESS if any(walk(rs) for rs in scenario.runs) else STABLE


def scenarios_for(data: dict) -> dict[str, Scenario]:
    """Rebuild the scenario objects behind a results.json (core or generated)."""
    from .generator import generate
    from .scenarios import SCENARIOS

    suite = data.get("suite", "core")
    m = re.match(r"generated\(n=(\d+), seed=(\d+)\)", suite)
    pool = generate(int(m.group(1)), int(m.group(2))) if m else SCENARIOS
    return {s.id: s for s in pool}


def tiers_for(data: dict) -> dict[str, str]:
    return {sid: tier(s) for sid, s in scenarios_for(data).items()}
