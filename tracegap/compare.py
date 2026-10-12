"""Compare two results.json files: ``python -m tracegap.compare OLD NEW``.

A regression is a case that was complete (or faithful) in OLD and is not in
NEW. Used by CI to fail only when trace quality gets worse.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _index(data: dict) -> dict:
    return {(r["adapter"], r["scenario"], r["mode"]): r for r in data["results"]}


def compare(old: dict, new: dict) -> dict:
    a, b = _index(old), _index(new)
    regressions, improvements = [], []
    for key in sorted(set(a) & set(b)):
        for axis in ("complete", "faithful"):
            if a[key][axis] and not b[key][axis]:
                regressions.append((key, axis, b[key]["failures"] + b[key]["fidelity_failures"]))
            elif not a[key][axis] and b[key][axis]:
                improvements.append((key, axis))
    return {
        "regressions": regressions,
        "improvements": improvements,
        "new_cases": sorted(set(b) - set(a)),
        "removed_cases": sorted(set(a) - set(b)),
    }


def render_comparison(d: dict) -> str:
    lines = [f"TraceGap comparison: {len(d['regressions'])} regression(s), {len(d['improvements'])} improvement(s), "
             f"{len(d['new_cases'])} new case(s), {len(d['removed_cases'])} removed case(s)"]
    for (ad, s, m), axis, why in d["regressions"]:
        lines.append(f"  REGRESSED {ad} {s} {m} ({axis})" + (f": {why[0]}" if why else ""))
    for (ad, s, m), axis in d["improvements"]:
        lines.append(f"  improved  {ad} {s} {m} ({axis})")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("old")
    p.add_argument("new")
    a = p.parse_args()
    d = compare(json.loads(Path(a.old).read_text()), json.loads(Path(a.new).read_text()))
    print(render_comparison(d))
    sys.exit(1 if d["regressions"] else 0)


if __name__ == "__main__":
    main()
