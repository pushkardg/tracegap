#!/usr/bin/env python3
"""Refresh the leaderboard table in README.md from the results files.

    python scripts/update_readme.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracegap.report import pct, tiered  # noqa: E402


def table() -> str:
    core = json.loads((ROOT / "results/results.json").read_text())
    gp = ROOT / "results/generated/results.json"
    gen = json.loads(gp.read_text()) if gp.exists() else None
    t = tiered(core, gen)
    caps = " | ".join(t["capabilities"])
    lines = [f"| # | Framework / surface | Version | Complete | Faithful | {caps} | Stress: complete |",
             "|---|---|---|---|---|" + "---|" * len(t["capabilities"]) + "---|"]
    for i, k in enumerate(t["order"], 1):
        r = t["rows"][k]
        c, f, n = r["stable"]
        sc, _, sn = r["stress"]
        cap = " | ".join(("✅ " if a == b else "❌ " if a == 0 else "⚠️ ") + f"{a}/{b}" for a, b in r["caps"])
        lines.append(f"| {i} | `{k}` | {r['version']} | **{pct(c, n)}** | {pct(f, n)} | {cap} | {pct(sc, sn)} |")
    sc, _, sn = t["stable"]
    rc, _, rn = t["stress"]
    lines.append("")
    lines.append(f"Stable tier: {sc:,} of {sn:,} cases complete ({pct(sc, sn)}). "
                 f"Stress tier: {rc:,} of {rn:,} ({pct(rc, rn)}).")
    return "\n".join(lines)


def main() -> None:
    p = ROOT / "README.md"
    s = p.read_text()
    new = re.sub(r"(<!-- LEADERBOARD:START -->\n).*?(\n?<!-- LEADERBOARD:END -->)",
                 lambda m: m.group(1) + table() + "\n<!-- LEADERBOARD:END -->", s, flags=re.S)
    p.write_text(new)
    print("README leaderboard updated" if new != s else "README leaderboard unchanged")


if __name__ == "__main__":
    main()
