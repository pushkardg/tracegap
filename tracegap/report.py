"""Turn results.json into a Markdown leaderboard: ``python -m tracegap.report``."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.1f}%"


def summarize(data: dict, tier: str | None = None) -> dict:
    """Per-surface counters. With ``tier`` ("stable" or "stress"), only cases of
    scenarios in that tier are counted (see tracegap/tiers.py)."""
    tmap = None
    if tier is not None:
        from .tiers import tiers_for

        tmap = tiers_for(data)
    by = defaultdict(list)
    for r in data["results"]:
        if tmap is not None and tmap.get(r["scenario"]) != tier:
            continue
        by[r["adapter"]].append(r)
    rows = {}
    for key, rs in by.items():
        s = lambda f: sum(r[f] for r in rs)  # noqa: E731
        rows[key] = {
            "cases": len(rs),
            "complete": sum(r["complete"] for r in rs),
            "faithful": sum(r["faithful"] for r in rs),
            "passed": sum(r["passed"] for r in rs),
            "recall": (s("executed_recorded"), s("executed")),
            "status": (s("status_correct"), s("status_checked")),
            "misreported_ok": s("misreported_ok"),
            "attempts": (s("unexecuted_visible"), s("unexecuted")),
            "args": (s("args_exact"), s("args_checked")),
            "output": (s("output_exact"), s("output_checked")),
            "phantoms": s("phantoms"),
            "duplicates": s("duplicates"),
            "isolation": s("isolation_violations"),
            "fragmented": s("fragmented_runs"),
            "orphaned_cases": sum(1 for r in rs if r["orphaned_tools"]),
        }
    return rows


def render(data: dict) -> str:
    rows = summarize(data)
    order = sorted(rows, key=lambda k: (-rows[k]["complete"], -rows[k]["faithful"], k))
    out = []
    out.append(f"# TraceGap {data['version']} results\n")
    out.append(f"Generated {data['generated_at']} on Python {data['python']}. "
               f"{len(data['scenarios'])} scenarios x 2 modes = {2 * len(data['scenarios'])} cases per surface.\n")
    out.append("## Leaderboard\n")
    out.append("| Framework / surface | Complete | Faithful | Executed calls recorded | Status correct | "
               "Failed calls shown as success | Unexecuted attempts visible | Args exact | Output/error exact |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for k in order:
        r = rows[k]
        out.append(
            f"| {k} | {r['complete']}/{r['cases']} | {r['faithful']}/{r['cases']} | "
            f"{pct(*r['recall'])} | {pct(*r['status'])} | {r['misreported_ok']} | "
            f"{r['attempts'][0]}/{r['attempts'][1]} | {pct(*r['args'])} | {pct(*r['output'])} |"
        )
    out.append("\nComplete = every call present with an honest status, no phantoms or duplicates, runs neither "
               "mixed nor fragmented. Faithful = every captured argument, output and error message exact. "
               "n/a = the surface does not capture that field.\n")

    out.append("## Scenario matrix\n")
    out.append("C = complete, F = faithful, `-` = failed. Left of the slash is invoke mode, right is stream mode.\n")
    scns = list(data["scenarios"])
    out.append("| Scenario | " + " | ".join(order) + " |")
    out.append("|---|" + "---|" * len(order))
    cell = {}
    for r in data["results"]:
        cell[(r["adapter"], r["scenario"], r["mode"])] = ("C" if r["complete"] else "-") + ("F" if r["faithful"] else "-")
    for sid in scns:
        title = data["scenarios"][sid]["title"]
        vals = [f"{cell.get((k, sid, 'invoke'), '?')}/{cell.get((k, sid, 'stream'), '?')}" for k in order]
        out.append(f"| {sid} {title} | " + " | ".join(vals) + " |")

    out.append("\n## Every failure\n")
    for k in order:
        fails = [r for r in data["results"] if r["adapter"] == k and not r["passed"]]
        if not fails:
            continue
        out.append(f"### {k}\n")
        for r in fails:
            for f in r["failures"]:
                out.append(f"- {r['scenario']} {r['mode']}: **completeness**: {f}")
            for f in r["fidelity_failures"]:
                out.append(f"- {r['scenario']} {r['mode']}: fidelity: {f}")
        out.append("")
    orphan = [(r["adapter"], r["scenario"], r["mode"]) for r in data["results"] if r["orphaned_tools"]]
    if orphan:
        out.append("## Tools still running after the run ended (informational)\n")
        for a, s, m in orphan:
            out.append(f"- {a} {s} {m}")
    out.append("\n## Versions\n")
    for k, v in data["adapters"].items():
        out.append(f"- {k}: {v['version']}")
    return "\n".join(out) + "\n"


# Capability columns: core scenarios in the Stable tier, grouped by what they test.
CAPABILITIES = [
    ("Tool failures", ["S05", "S06"]),
    ("Cancellation", ["S17", "S18"]),
    ("Rejected calls", ["S08", "S09", "S10"]),
    ("Nested agents", ["S22"]),
]


def tiered(core: dict, generated: dict | None = None) -> dict:
    """Structured Stable/Stress leaderboard data (core + generated suites)."""
    from .tiers import tiers_for

    docs = [core] + ([generated] if generated else [])
    tagged = []
    for d in docs:
        tm = tiers_for(d)
        tagged += [dict(r, tier=tm[r["scenario"]]) for r in d["results"]]
    versions = {k: v["version"] for d in docs for k, v in d["adapters"].items()}
    by = defaultdict(list)
    for r in tagged:
        by[r["adapter"]].append(r)

    def counts(rs):
        return sum(r["complete"] for r in rs), sum(r["faithful"] for r in rs), len(rs)

    rows = {}
    for k, rs in by.items():
        st = [r for r in rs if r["tier"] == "stable"]
        sr = [r for r in rs if r["tier"] == "stress"]
        caps = []
        for _, ids in CAPABILITIES:
            sel = [r for r in st if r["scenario"] in ids]
            caps.append((sum(r["complete"] for r in sel), len(sel)))
        rows[k] = {"version": versions[k].split(",")[0], "stable": counts(st), "stress": counts(sr), "caps": caps}
    order = sorted(rows, key=lambda k: (-rows[k]["stable"][0] / max(1, rows[k]["stable"][2]),
                                        -rows[k]["stable"][1], k))
    st_all = [r for r in tagged if r["tier"] == "stable"]
    sr_all = [r for r in tagged if r["tier"] == "stress"]
    return {"order": order, "rows": rows, "stable": counts(st_all), "stress": counts(sr_all),
            "capabilities": [n for n, _ in CAPABILITIES]}


def leaderboard(core: dict, generated: dict | None = None) -> str:
    """Top-level leaderboard: Stable tier first (core + generated), capability
    columns from the core suite, then the Stress tier separately."""
    t = tiered(core, generated)
    rows, order = t["rows"], t["order"]
    out = ["# TraceGap agent trace reliability leaderboard", ""]
    out.append(f"Benchmark {core['version']}. Primary ranking uses **Stable** cases only: scenarios whose verdicts "
               "were identical across repeated full runs, so your score does not change when you run it again. "
               "**Stress** cases (a tool raising inside a parallel batch) are reported separately because some "
               "frameworks handle them with scheduling-dependent races. See `tracegap/tiers.py`.")
    out.append("")
    sc, _, sn = t["stable"]
    rc, _, rn = t["stress"]
    out.append(f"Stable: {sc} of {sn} cases complete ({pct(sc, sn)}). Stress: {rc} of {rn} ({pct(rc, rn)}).")
    out.append("")
    out.append("## Stable tier")
    out.append("")
    cap_head = " | ".join(t["capabilities"])
    out.append(f"| # | Framework / surface | Version | Complete | Faithful | {cap_head} |")
    out.append("|---|---|---|---|---|" + "---|" * len(t["capabilities"]))
    for i, k in enumerate(order, 1):
        r = rows[k]
        c, f, n = r["stable"]
        caps = " | ".join(f"{a}/{b}" for a, b in r["caps"])
        out.append(f"| {i} | {k} | {r['version']} | {c}/{n} ({pct(c, n)}) | {f}/{n} ({pct(f, n)}) | {caps} |")
    out.append("")
    out.append("Complete: every call present with an honest status, no phantoms or duplicates, runs neither mixed "
               "nor fragmented. Faithful: every captured argument, output and error message exact. Capability "
               "columns count complete Stable cases among the scenarios that test it: tool failures S05–S06, "
               "cancellation S17–S18, rejected calls S08–S10, nested agents S22 (each in invoke and stream mode).")
    out.append("")
    out.append("## Stress tier")
    out.append("")
    out.append("| Framework / surface | Complete | Faithful |")
    out.append("|---|---|---|")
    for k in order:
        c, f, n = rows[k]["stress"]
        out.append(f"| {k} | {c}/{n} ({pct(c, n)}) | {f}/{n} ({pct(f, n)}) |")
    out.append("")
    out.append("Per-suite detail, scenario matrix and every failure reason: `results/CORE.md` and "
               "`results/generated/LEADERBOARD.md`.")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="?", default="results/results.json")
    p.add_argument("--out", default="results/CORE.md")
    p.add_argument("--generated", default="results/generated/results.json",
                   help="with --leaderboard: generated-suite results to include")
    p.add_argument("--leaderboard", metavar="OUT", help="also write the tiered top-level leaderboard here")
    a = p.parse_args()
    data = json.loads(Path(a.results).read_text())
    Path(a.out).write_text(render(data))
    print(f"wrote {a.out}")
    if a.leaderboard:
        gen = json.loads(Path(a.generated).read_text()) if Path(a.generated).exists() else None
        Path(a.leaderboard).write_text(leaderboard(data, gen))
        print(f"wrote {a.leaderboard}")


if __name__ == "__main__":
    main()
