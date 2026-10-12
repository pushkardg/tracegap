"""Figure: core-suite completeness across releases, for surfaces whose
completeness changed. Reads results/HISTORY.md.

    python analysis/fig_history.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from analyze import BLUE, GRID, INK, INK2, OUT, style  # noqa: E402

NOTES = {  # version -> (note, text y position); from results/HISTORY.md
    "smolagents/memory": {"1.18.0": ("parallel calls: a failed\nstep loses its calls", 42.5),
                          "1.20.0": ("duplicate ids dropped", 33.5)},
    "openai-agents/tracing": {"0.20.0": ("rejects duplicate ids", 32.0)},
    "pydantic-ai/otel": {"2.30.0": ("rejected calls\nbecome visible", 30.0)},
    "crewai/events": {"1.15.23": ("unknown-tool calls\nbecome visible", 33.0)},
}


def parse():
    t = (ROOT / "results/HISTORY.md").read_text()
    out = {}
    for sec in re.split(r"^## ", t, flags=re.M)[1:]:
        name = sec.splitlines()[0].strip()
        rows = re.findall(r"^\| ([0-9][^|]*?) \| (\d{4})-(\d\d)-(\d\d) \| (\d+)/44 \| (\d+)/44 \|", sec, re.M)
        pts = sorted((date(int(y), int(m), int(d)), v.strip(), int(c)) for v, y, m, d, c, _ in rows)
        if pts:
            out[name] = pts
    return out


def main():
    import matplotlib.pyplot as plt

    style(plt)
    h = parse()
    changed = [k for k, v in h.items() if len({c for _, _, c in v}) > 1]
    n = len(changed)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6.8, 2.1 * rows), sharey=True)
    axes = axes.ravel()
    for ax, k in zip(axes, changed):
        pts = h[k]
        xs = list(range(len(pts)))
        ys = [p[2] for p in pts]
        ax.step(xs, ys, where="post", color=BLUE, lw=2)
        ax.plot(xs, ys, "o", color=BLUE, ms=3.5, mec="white", mew=0.7, clip_on=False)
        ax.set_title(k, fontsize=7, color=INK, loc="left")
        ax.set_ylim(24, 46)
        ax.set_yticks([28, 36, 44])
        ax.grid(axis="y", color=GRID, lw=0.5)
        ax.set_axisbelow(True)
        ax.set_xticks(xs, [p[1] for p in pts], rotation=60, ha="right", fontsize=5.5)
        ax.tick_params(axis="y", labelsize=6)
        ax.set_xlim(-0.5, len(pts) - 0.5)
        for i, (d, v, c) in enumerate(pts):
            note = NOTES.get(k, {}).get(v)
            if note:
                txt, ty = note
                right = i > len(pts) / 2
                ax.annotate(f"{v}: {txt}", (i, c), xytext=(i + (-0.3 if right else 0.3), ty), textcoords="data",
                            fontsize=5.5, color=INK2, ha="right" if right else "left", va="center",
                            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))
    for ax in axes[n:]:
        ax.axis("off")
    for ax in axes[::cols]:
        ax.set_ylabel("core complete\n(of 44)", fontsize=6.5)
    fig.tight_layout(h_pad=1.0, w_pad=0.6)
    fig.savefig(OUT / "fig_history.pdf")
    print("surfaces:", changed)


if __name__ == "__main__":
    main()
