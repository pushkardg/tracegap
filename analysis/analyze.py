"""Analyses for the paper: bootstrap CIs, scenario categories, generated-suite conditions,
metric ablation, ranking agreement across seeds, cost. Reads results/, writes
analysis/out/analysis.json and figures (analysis/out/fig_*.pdf). LaTeX is written by make_tables.py.

    python analysis/analyze.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tracegap.adapters.reference import _validate  # noqa: E402
from tracegap.generator import generate  # noqa: E402
from tracegap.report import tiered  # noqa: E402
from tracegap.scenarios import SCENARIOS  # noqa: E402
from tracegap.tasks import defects_from  # noqa: E402
from tracegap.tiers import RAISING_TOOLS, STABLE, tier  # noqa: E402
from tracegap.tools import TOOLS  # noqa: E402

OUT = ROOT / "analysis" / "out"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(0)

# Reference palette (dataviz skill, light mode). Slots 1-3 only: validated all-pairs.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SEQ = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def load():
    core = json.loads((ROOT / "results/results.json").read_text())
    gen = json.loads((ROOT / "results/generated/results.json").read_text())
    return core, gen


def short(k: str) -> str:
    return k.replace("openinference", "OI").replace("semantic-kernel", "sem-kernel")


# --------------------------------------------------------------- A. bootstrap CIs

def bootstrap(core, gen, reps=2000, table_order=None):
    scn = {s.id: s for s in SCENARIOS} | {s.id: s for s in generate(200, 1)}
    rows = [r for d in (core, gen) for r in d["results"] if tier(scn[r["scenario"]]) == STABLE]
    by = defaultdict(lambda: defaultdict(list))  # surface -> scenario -> [complete...]
    for r in rows:
        by[r["adapter"]][r["scenario"]].append(r["complete"])
    sids = sorted({r["scenario"] for r in rows})
    surfaces = sorted(by)
    mat = np.array([[np.mean(by[a][s]) for s in sids] for a in surfaces])  # surface x scenario
    point = mat.mean(axis=1)
    idx = RNG.integers(0, len(sids), size=(reps, len(sids)))
    boots = mat[:, idx].mean(axis=2)  # surface x reps
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=1)
    order = ([surfaces.index(k) for k in table_order] if table_order else list(np.argsort(-point, kind="stable")))
    res = {surfaces[i]: {"point": float(point[i]), "lo": float(lo[i]), "hi": float(hi[i])} for i in order}
    # adjacent rank separations: share of bootstrap samples preserving the order
    ranked = [surfaces[i] for i in order]
    sep = []
    for a, b in zip(ranked, ranked[1:]):
        ia, ib = surfaces.index(a), surfaces.index(b)
        sep.append({"higher": a, "lower": b, "p_higher": float(np.mean(boots[ia] > boots[ib])),
                    "p_ge": float(np.mean(boots[ia] >= boots[ib]))})
    # how many distinct "tiers of rank": groups where adjacent p_higher < 0.95
    return {"n_scenarios": len(sids), "reps": reps, "ci": res, "adjacent": sep}


# --------------------------------------------------------------- B. category x surface

def category_matrix(core):
    cats = []
    for s in SCENARIOS:
        if s.category not in cats:
            cats.append(s.category)
    cat_of = {s.id: s.category for s in SCENARIOS}
    t = defaultdict(lambda: defaultdict(list))
    for r in core["results"]:
        t[r["adapter"]][cat_of[r["scenario"]]].append(r["complete"])
    return cats, {a: {c: (sum(v[c]), len(v[c])) for c in cats} for a, v in t.items()}


# --------------------------------------------------------------- C. conditions in the generated suite

def features(s):
    calls = [c for r in s.runs for rr in ([r] + ([r.nested] if r.nested else [])) for t in rr.turns for c in t.calls]
    rejected = 0
    for c in calls:
        if c.name not in s.tools or c.name not in TOOLS:
            rejected += 1 if c.name != "delegate" else 0
            continue
        try:
            _validate(TOOLS[c.name], c.args)
        except TypeError:
            rejected += 1
    ending = s.description.split("ending ")[-1].split("'")[1]
    return {
        "calls": len(calls),
        "turns": sum(len(r.turns) for r in s.runs),
        "parallel": any(len(t.calls) > 1 for r in s.runs for rr in ([r] + ([r.nested] if r.nested else [])) for t in rr.turns),
        "raising_tool": any(c.name in RAISING_TOOLS for c in calls),
        "stress": tier(s) != STABLE,
        "rejected": rejected > 0,
        "cancelled": ending in ("cancel_after", "cancel_in_tool"),
        "model_error": ending == "model_error",
        "limit": ending == "limit",
        "concurrent": len(s.runs) > 1,
        "nested": any(r.nested for r in s.runs),
        "sync_tool": any(c.name == "echo_sync" for c in calls),
        "large_output": any(c.name == "big" for c in calls),
    }


CONDS = [("parallel", "parallel calls in a turn"), ("raising_tool", "a tool raises"),
         ("stress", "a tool raises inside a parallel batch (Stress)"), ("rejected", "a call is rejected"),
         ("cancelled", "run is cancelled"), ("model_error", "model call fails"), ("limit", "turn limit reached"),
         ("concurrent", "two concurrent runs"), ("nested", "nested agent"), ("sync_tool", "synchronous tool"),
         ("large_output", "large output")]


def conditions(gen):
    feats = {s.id: features(s) for s in generate(200, 1)}
    res = gen["results"]
    out = []
    for key, label in CONDS:
        w = [r["complete"] for r in res if feats[r["scenario"]][key]]
        wo = [r["complete"] for r in res if not feats[r["scenario"]][key]]
        nsc = sum(1 for f in feats.values() if f[key])
        out.append({"key": key, "label": label, "scenarios": nsc, "with": float(np.mean(w)), "without": float(np.mean(wo)),
                    "n_with": len(w), "n_without": len(wo)})
    # logistic regression of completeness on conditions (pooled, with surface fixed effects)
    from sklearn.linear_model import LogisticRegression

    surfaces = sorted({r["adapter"] for r in res})
    keys = [k for k, _ in CONDS if k != "stress"]
    X, y = [], []
    for r in res:
        f = feats[r["scenario"]]
        X.append([float(f[k]) for k in keys] + [np.log1p(f["calls"])] + [float(r["adapter"] == a) for a in surfaces[1:]])
        y.append(int(r["complete"]))
    lr = LogisticRegression(C=10.0, max_iter=5000).fit(np.array(X), np.array(y))
    coefs = {k: float(c) for k, c in zip(keys + ["log1p_calls"], lr.coef_[0][: len(keys) + 1])}
    # completeness vs number of calls (binned), pooled and for three surfaces
    bins = [(1, 3), (4, 6), (7, 10), (11, 15), (16, 99)]
    curve = {}
    for a in ["all"] + surfaces:
        pts = []
        for lo, hi in bins:
            v = [r["complete"] for r in res if lo <= feats[r["scenario"]]["calls"] <= hi and (a == "all" or r["adapter"] == a)]
            pts.append((f"{lo}-{hi}" if hi < 99 else f"{lo}+", float(np.mean(v)) if v else None, len(v)))
        curve[a] = pts
    return {"conditions": out, "logit": coefs, "curve": curve,
            "calls_total": sum(f["calls"] for f in feats.values())}


# --------------------------------------------------------------- D. metric ablation

def ablation(core, gen):
    res = core["results"] + gen["results"]
    inc = [r for r in res if not r["complete"]]
    lab = [set(defects_from(r["failures"], [])) for r in inc]
    total = len(res)
    cnt = Counter(d for s in lab for d in s)
    only = Counter(next(iter(s)) for s in lab if len(s) == 1)
    # A naive metric: recall of executed calls only (would it notice?)
    naive_miss = sum(1 for s in lab if "missing_call" not in s)
    # Recall + status (no attempts, no isolation)
    rs_miss = sum(1 for s in lab if not (s & {"missing_call", "false_success", "status_mismatch", "duplicate", "phantom"}))
    return {"cases": total, "incomplete": len(inc), "by_defect": dict(cnt), "only_reason": dict(only),
            "recall_only_misses": naive_miss, "recall_status_misses": rs_miss}


# --------------------------------------------------------------- E. ranking agreement

def kendall(a: dict, b: dict) -> float:
    from scipy.stats import kendalltau

    ks = sorted(set(a) & set(b))
    return float(kendalltau([a[k] for k in ks], [b[k] for k in ks]).statistic)


def stable_rates(d):
    scn = {s.id: s for s in SCENARIOS}
    m = __import__("re").match(r"generated\(n=(\d+), seed=(\d+)\)", d.get("suite", "core"))
    if m:
        scn = {s.id: s for s in generate(int(m.group(1)), int(m.group(2)))}
    t = defaultdict(list)
    for r in d["results"]:
        if tier(scn[r["scenario"]]) == STABLE:
            t[r["adapter"]].append(r["complete"])
    return {k: float(np.mean(v)) for k, v in t.items()}


def agreement(core, gen):
    out = {"core_vs_generated_stable": kendall(stable_rates(core), stable_rates(gen))}
    seeds = {}
    for p in sorted((ROOT / "results/seeds").glob("seed*/results.json")):
        d = json.loads(p.read_text())
        if len(d["results"]) < 15 * 200:
            continue
        seeds[p.parent.name] = stable_rates(d)
    base = stable_rates(gen)
    for name, rates in seeds.items():
        out[f"seed1_vs_{name}"] = kendall(base, rates)
        out[f"{name}_rates"] = rates
    names = sorted(seeds)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out[f"{names[i]}_vs_{names[j]}"] = kendall(seeds[names[i]], seeds[names[j]])
    out["seed1_rates"] = base
    return out


# --------------------------------------------------------------- F. cost

def cost(core, gen):
    by = defaultdict(list)
    for r in core["results"] + gen["results"]:
        by[r["adapter"]].append(r["seconds"])
    return {k: {"median_s": float(np.median(v)), "total_min": float(np.sum(v) / 60)} for k, v in sorted(by.items())}


# --------------------------------------------------------------- figures

def style(plt):
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 8,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "savefig.bbox": "tight", "savefig.dpi": 300,
    })


def fig_ci(boot):
    import matplotlib.pyplot as plt

    style(plt)
    items = list(boot["ci"].items())[::-1]
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    for i, (k, v) in enumerate(items):
        ax.plot([v["lo"] * 100, v["hi"] * 100], [i, i], color=BLUE, lw=2, solid_capstyle="round")
        ax.plot(v["point"] * 100, i, "o", color=BLUE, ms=4, mec="white", mew=0.8, clip_on=False)
    ax.set_yticks(range(len(items)), [short(k) for k, _ in items], fontsize=7, color=INK)
    ax.set_xlabel("Stable-tier cases complete (%), 95% bootstrap CI")
    ax.grid(axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.set_xlim(0, 102)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    fig.savefig(OUT / "fig_ci.pdf")
    plt.close(fig)


def fig_categories(cats, mat):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    style(plt)
    surfaces = sorted(mat, key=lambda a: -sum(x[0] for x in mat[a].values()))
    vals = np.array([[mat[a][c][0] / mat[a][c][1] for c in cats] for a in surfaces])
    fig, ax = plt.subplots(figsize=(3.4, 3.4))
    cmap = ListedColormap(SEQ)
    ax.imshow(1 - vals, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, a in enumerate(surfaces):
        for j, c in enumerate(cats):
            n, d = mat[a][c]
            ink = "white" if (1 - n / d) > 0.55 else INK
            ax.text(j, i, f"{n}/{d}", ha="center", va="center", fontsize=6, color=ink)
    ax.set_xticks(range(len(cats)), cats, rotation=35, ha="right", fontsize=7, color=INK)
    ax.set_yticks(range(len(surfaces)), [short(a) for a in surfaces], fontsize=7, color=INK)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(cats)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(surfaces)), minor=True)
    ax.grid(which="minor", color="white", lw=1.5)
    ax.tick_params(which="minor", length=0)
    fig.savefig(OUT / "fig_categories.pdf")
    plt.close(fig)


def fig_curve(cond):
    import matplotlib.pyplot as plt

    style(plt)
    fig, ax = plt.subplots(figsize=(3.3, 2.2))
    picks = [("all", "all surfaces", INK2, "-"), ("google-adk/otel", "google-adk/otel", BLUE, "-"),
             ("langgraph/callbacks", "langgraph/callbacks", ORANGE, "-"), ("smolagents/memory", "smolagents/memory", AQUA, "-")]
    for key, lab, col, ls in picks:
        pts = cond["curve"][key]
        xs = list(range(len(pts)))
        ys = [p[1] * 100 for p in pts]
        ax.plot(xs, ys, ls, color=col, lw=2, marker="o", ms=4, mec="white", mew=0.8, label=lab)
    ax.set_xticks(range(len(cond["curve"]["all"])), [p[0] for p in cond["curve"]["all"]])
    ax.set_xlabel("tool calls in the scenario")
    ax.set_ylabel("cases complete (%)")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2)
    fig.savefig(OUT / "fig_calls.pdf")
    plt.close(fig)


def main():
    core, gen = load()
    boot = bootstrap(core, gen, table_order=tiered(core, gen)["order"])
    cats, mat = category_matrix(core)
    cond = conditions(gen)
    abl = ablation(core, gen)
    agr = agreement(core, gen)
    cst = cost(core, gen)
    tt = tiered(core, gen)
    out = {"bootstrap": boot, "categories": {"cats": cats, "matrix": mat}, "conditions": cond, "ablation": abl,
           "agreement": agr, "cost": cst, "stable_total": tt["stable"], "stress_total": tt["stress"]}
    (OUT / "analysis.json").write_text(json.dumps(out, indent=1))
    fig_ci(boot)
    fig_categories(cats, mat)
    fig_curve(cond)
    print(json.dumps({k: v for k, v in out.items() if k not in ("categories",)}, indent=1)[:6000])


if __name__ == "__main__":
    main()
