"""Use TraceGap from your own test suite.

Example (no pytest-asyncio needed)::

    import pytest
    from tracegap.testing import cases, check

    from myframework_tracegap import MyAdapter

    @pytest.mark.parametrize("case", cases(MyAdapter, known_gaps={"S08"}))
    def test_tracegap(case):
        check(case)

Each scenario/mode pair becomes its own test. Only Stable-tier scenarios are
included by default (see tracegap/tiers.py), so results do not depend on
scheduling. Scenarios listed in
``known_gaps`` are marked xfail(strict=True): the test suite tells you when a
gap is fixed, and fails if a passing scenario breaks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .harness import Adapter, CaseResult, run_case
from .scenarios import MODES, SCENARIOS, Scenario


@dataclass
class Case:
    adapter_factory: Callable[[], Adapter]
    scenario: Scenario
    mode: str
    require_faithful: bool = True

    def __repr__(self) -> str:
        return f"{self.scenario.id}-{self.mode}"


def cases(
    adapter_factory: Callable[[], Adapter],
    scenarios: Optional[Iterable[str]] = None,
    modes: Optional[Iterable[str]] = None,
    known_gaps: Iterable[str] = (),
    require_faithful: bool = True,
    tier: str = "stable",
):
    """Defaults to the Stable tier so CI results do not depend on scheduling.
    Pass tier="all" (or "stress") to include race-sensitive scenarios."""
    import pytest

    from .tiers import tier as tier_of

    wanted = set(scenarios) if scenarios else None
    gaps = set(known_gaps)
    params = []
    for s in SCENARIOS:
        if wanted and s.id not in wanted:
            continue
        if tier != "all" and tier_of(s) != tier:
            continue
        for m in modes or MODES:
            marks = [pytest.mark.xfail(strict=True, reason="known TraceGap gap")] if s.id in gaps or f"{s.id}-{m}" in gaps else []
            params.append(pytest.param(Case(adapter_factory, s, m, require_faithful), id=f"{s.id}-{m}", marks=marks))
    return params


def run(case: Case) -> CaseResult:
    return asyncio.run(run_case(case.adapter_factory(), case.scenario, case.mode))


def check(case: Case) -> CaseResult:
    r = run(case)
    problems = list(r.failures) + (list(r.fidelity_failures) if case.require_faithful else [])
    assert not problems, f"{case.scenario.id} ({case.scenario.title}), {case.mode} mode:\n  " + "\n  ".join(problems)
    return r
