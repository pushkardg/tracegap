#!/usr/bin/env python3
"""Summarise the version matrix: per framework/surface, how completeness and
fidelity changed across releases, and which scenarios changed verdict.

    python scripts/history_report.py > results/HISTORY.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VDIR = ROOT / "results" / "versions"


def vkey(v: str):
    return tuple(int(x) if x.isdigit() else 0 for x in v.replace("post", ".").split("."))


def calibrated(rs) -> bool:
    """S01 (one successful call) is the calibration case: if a surface fails it,
    the surface is absent in that version or reports in a format the current
    adapter does not read, so the version is left out of the history."""
    s01 = [r for r in rs if r["scenario"] == "S01"]
    return bool(s01) and all(r["passed"] for r in s01)


def main() -> None:
    status = json.loads((VDIR / "status.json").read_text())
    per = defaultdict(dict)  # (adapter) -> version -> {(scn,mode): (complete, faithful)}
    released = {}
    uncalibrated = []
    for f in sorted(VDIR.glob("*/*.json")):
        fw, ver = f.parent.name, f.stem
        data = json.loads(f.read_text())
        st = status.get(f"{fw}=={ver}", {})
        if not data["results"] or st.get("harness_errors"):
            continue
        released[(fw, ver)] = st.get("released", "")
        by_adapter = defaultdict(list)
        for r in data["results"]:
            by_adapter[r["adapter"]].append(r)
        for adapter, rs in by_adapter.items():
            if not calibrated(rs):
                uncalibrated.append(f"{adapter} {ver}")
                continue
            for r in rs:
                per[adapter].setdefault(ver, {})[(r["scenario"], r["mode"])] = (
                    r["complete"], r["faithful"], r["executed"] + r["unexecuted"])

    lines = ["# TraceGap version history", ""]
    covered = sum(1 for s in status.values() if s.get("ok") and not s.get("harness_errors"))
    lines.append(f"Core suite (22 scenarios x 2 modes) run against {covered} released versions of 9 frameworks. "
                 "Each version's dependencies were resolved as of one day after its release where that still "
                 "installs; see results/versions/status.json for the resolution used per version.")
    lines.append("")
    missing = [k for k, s in status.items() if not s.get("ok") or s.get("harness_errors")]
    if missing:
        lines.append("Not covered: " + ", ".join(sorted(missing)) + ".")
        lines.append("")
    if uncalibrated:
        lines.append("Left out because the calibration case S01 (one successful call) fails, meaning the surface "
                     "is absent in that version or reports in a format the current adapter does not read: "
                     + ", ".join(sorted(uncalibrated)) + ".")
        lines.append("")
    for adapter in sorted(per):
        fw = adapter.split("/")[0]
        vers = sorted(per[adapter], key=vkey)
        lines.append(f"## {adapter}")
        lines.append("")
        lines.append("| Version | Released | Complete | Faithful |")
        lines.append("|---|---|---|---|")
        fwdir = {"openai-agents": "openai-agents", "pydantic-ai": "pydantic-ai", "langgraph": "langgraph",
                 "autogen": "autogen", "smolagents": "smolagents", "llamaindex": "llamaindex",
                 "semantic-kernel": "semantic-kernel", "google-adk": "google-adk", "crewai": "crewai"}[fw]
        for v in reversed(vers):
            cells = per[adapter][v]
            c = sum(x[0] for x in cells.values())
            fa = sum(x[1] for x in cells.values())  # noqa: F841
            lines.append(f"| {v} | {released.get((fwdir, v), '')} | {c}/{len(cells)} | {fa}/{len(cells)} |")
        lines.append("")
        changes = []
        for a, b in zip(vers, vers[1:]):
            for k in sorted(set(per[adapter][a]) & set(per[adapter][b])):
                (ca, fa, ea), (cb, fb, eb) = per[adapter][a][k], per[adapter][b][k]
                if (ca, fa) != (cb, fb):
                    def lab(c, f):
                        return ("complete" if c else "incomplete") + (", faithful" if f else ", unfaithful")
                    note = "" if ea == eb else (f" (the framework ran the scenario differently: {ea} -> {eb} "
                                                "calls emitted, so this may not be a tracing change)")
                    changes.append(f"- {a} -> {b}: {k[0]} {k[1]}: {lab(ca, fa)} -> {lab(cb, fb)}{note}")
        if changes:
            lines.append("Verdict changes between consecutive versions:")
            lines.append("")
            lines.extend(changes)
        else:
            lines.append("No verdict changed across the versions tested.")
        lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
