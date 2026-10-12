#!/usr/bin/env python3
"""Compare full runs of the same suite and report verdict stability.

    python scripts/stability.py RUN1.json RUN2.json [...] \
        [--known results/generated/unstable_cases.json] \
        [--out results/generated/STABILITY.md] [--write-unstable results/generated/unstable_cases.json]

A case is unstable if its (complete, faithful) verdict differs between any two
runs. --known adds cases found unstable by earlier runs that are no longer
stored (their keys are merged into the union).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracegap.tiers import STRESS, tiers_for  # noqa: E402


def verdicts(d: dict) -> dict:
    return {(r["adapter"], r["scenario"], r["mode"]): (r["complete"], r["faithful"]) for r in d["results"]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("runs", nargs="+")
    p.add_argument("--known", help="earlier unstable_cases.json to merge")
    p.add_argument("--earlier-runs", type=int, default=0, help="number of earlier runs represented by --known")
    p.add_argument("--out")
    p.add_argument("--write-unstable")
    a = p.parse_args()
    docs = [json.loads(Path(f).read_text()) for f in a.runs]
    vs = [verdicts(d) for d in docs]
    keys = set(vs[0])
    for v in vs[1:]:
        assert set(v) == keys, "runs cover different cases"
    new = {k for k in keys if len({v[k] for v in vs}) > 1}
    known = {tuple(k) for k in json.loads(Path(a.known).read_text())} if a.known else set()
    unstable = new | known
    tm = tiers_for(docs[-1])
    # differing cases found by the first two runs, then added by each later run
    seen, parts = set(), []
    for i in range(1, len(vs)):
        found = {k for k in keys if len({v[k] for v in vs[: i + 1]}) > 1} - seen
        parts.append(f"runs 1-{i + 1}: {len(found)}" if i == 1 else f"run {i + 1} added {len(found)}")
        seen |= found
    incremental = "Differing cases by run: " + "; ".join(parts) + (
        f"; plus {len(known - new)} from earlier runs not stored here." if known - new else ".")
    outside = sorted(k for k in unstable if tm[k[1]] != STRESS)
    n_runs = len(vs) + a.earlier_runs
    by = Counter(k[0] for k in unstable)
    lines = [
        f"# Verdict stability: {docs[-1].get('suite', '?')} suite",
        "",
        f"The suite ({docs[-1].get('suite', '?')}; {len(keys):,} cases) has been run in full {n_runs} times. "
        f"{len(keys) - len(unstable):,} of {len(keys):,} verdicts ({100 * (len(keys) - len(unstable)) / len(keys):.1f}%) "
        f"were identical in every run; {len(unstable)} differed in at least one.",
        "",
        f"Every case that differed is in the **Stress** tier (a tool raises inside a parallel batch)"
        if not outside else f"WARNING: {len(outside)} unstable cases are outside the Stress tier: {outside[:10]}",
        "",
        "| Surface | Cases that differed |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in by.most_common()]
    lines += [
        "",
        incremental,
        "",
        "Benchmark version of each run: " + ", ".join(f"{Path(f).stem} {d.get('version', '?')}" for f, d in zip(a.runs, docs))
        + " (the scorer did not change between these versions).",
        "",
        "What varies (from manual inspection of the generated-suite cases): in Pydantic AI, whether a sibling call that succeeded gets its result recorded (history) or "
        "its span exported with its result (OpenTelemetry) before the run aborts; in LangGraph, whether a sibling "
        "had started executing when the run aborted. These are races inside the frameworks, so the leaderboard "
        "ranks only the Stable tier and reports the Stress tier separately.",
        "",
        "The published numbers are from the latest run. The cases are listed in `unstable_cases.json` and flagged "
        "`stable=false` in the Hugging Face dataset. Recompute with "
        f"`python scripts/stability.py {' '.join(a.runs)}`.",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if a.out:
        Path(a.out).write_text(text)
    if a.write_unstable:
        Path(a.write_unstable).write_text(json.dumps(sorted(list(k) for k in unstable)))
    if outside:
        sys.exit(1)


if __name__ == "__main__":
    main()
