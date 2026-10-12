"""Tests for the seeded generator, the merge tool, and the version-history helpers."""

import asyncio
import json
from dataclasses import asdict

import pytest

from tracegap.adapters.reference import ReferenceAdapter
from tracegap.generator import generate
from tracegap.harness import run_case
from tracegap.merge import merge


def test_generator_is_deterministic():
    a = [asdict(s) for s in generate(50, seed=3)]
    b = [asdict(s) for s in generate(50, seed=3)]
    assert a == b
    assert a != [asdict(s) for s in generate(50, seed=4)]


def test_generated_tags_are_unique_and_ids_embed_seed():
    for s in generate(100, seed=1):
        assert s.id.startswith("G1-")
        tags = []

        def walk(rs):
            for t in rs.turns:
                tags.extend(c.args["tag"] for c in t.calls)
            if rs.nested:
                walk(rs.nested)

        for rs in s.runs:
            walk(rs)
        assert len(tags) == len(set(tags)), s.id


@pytest.mark.parametrize("scenario", generate(24, seed=11), ids=lambda s: s.id)
def test_reference_passes_generated_sample(scenario):
    for mode in ("invoke", "stream"):
        r = asyncio.run(run_case(ReferenceAdapter(), scenario, mode))
        assert r.passed, (scenario.description, r.failures, r.fidelity_failures)


def _doc(adapter, version, scenario="S01"):
    return {
        "benchmark": "TraceGap", "version": "0.2.0", "suite": "core", "generated_at": "2026-10-04T00:00:00+00:00",
        "python": "3.13", "scenarios": {scenario: {"category": "basic", "title": "t", "description": "d"}},
        "adapters": {adapter: {"version": version, "capture": {}}},
        "results": [{"adapter": adapter, "scenario": scenario, "mode": "invoke", "complete": True, "faithful": True}],
    }


def test_merge_combines_and_rejects_conflicts():
    m = merge([_doc("a/x", "a 1"), _doc("b/y", "b 2")])
    assert set(m["adapters"]) == {"a/x", "b/y"} and len(m["results"]) == 2
    with pytest.raises(SystemExit):
        merge([_doc("a/x", "a 1"), _doc("a/x", "a 2")])


def test_status_files_are_json():
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "results" / "versions" / "status.json"
    if p.exists():
        data = json.loads(p.read_text())
        assert all("framework" in v for v in data.values())
