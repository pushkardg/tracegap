"""Turn analysis outputs into LaTeX for the TMLR paper (paper/tmlr/gen/).
All tables and most data-derived numbers in the paper are produced here; the
few numbers written directly in the text are listed in analysis/README.md.

    python analysis/make_tables.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tracegap.adapters.reference import DEFECTS  # noqa: E402
from tracegap.report import tiered  # noqa: E402
from tracegap.scenarios import SCENARIOS  # noqa: E402

A = ROOT / "analysis" / "out"
G = ROOT / "paper" / "tmlr" / "gen"
for _req in ("feature_ablation.json", "learned_baselines_tagged.json", "learned_baselines_allfeatures.json"):
    if not (A / _req).exists():  # check every input before writing anything
        raise SystemExit(f"missing analysis/out/{_req}: see analysis/README.md (full pipeline)")
G.mkdir(parents=True, exist_ok=True)
macros: dict[str, str] = {}


def M(name, val):
    macros[name] = val


def pct(a, b, d=1):
    return f"{100 * a / b:.{d}f}"


def num(n):
    return f"{n:,}".replace(",", "{,}")


def esc(s):
    return s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


core = json.loads((ROOT / "results/results.json").read_text())
gen = json.loads((ROOT / "results/generated/results.json").read_text())
an = json.loads((A / "analysis.json").read_text())
lb = json.loads((A / "learned_baselines.json").read_text())
mm = json.loads((A / "mutation_matrix.json").read_text())
mg_path = A / "mutation_generated.json"
mg = json.loads(mg_path.read_text()) if mg_path.exists() else None

# ---------------------------------------------------------------- headline numbers
cc = sum(r["complete"] for r in core["results"])
gc = sum(r["complete"] for r in gen["results"])
cp = sum(r["passed"] for r in core["results"])
M("coreComplete", num(cc)); M("coreCases", num(len(core["results"]))); M("corePct", pct(cc, len(core["results"])))
M("corePassed", num(cp)); M("corePassedPct", pct(cp, len(core["results"])))
M("genComplete", num(gc)); M("genCases", num(len(gen["results"]))); M("genPct", pct(gc, len(gen["results"])))
t = tiered(core, gen)
sc, sf, sn = t["stable"]
rc, rf, rn = t["stress"]
M("stableComplete", num(sc)); M("stableCases", num(sn)); M("stablePct", pct(sc, sn))
M("stableFaithful", num(sf)); M("stableFaithfulPct", pct(sf, sn))
M("stressComplete", num(rc)); M("stressCases", num(rn)); M("stressPct", pct(rc, rn))
M("genCalls", num(an["conditions"]["calls_total"]))

# ---------------------------------------------------------------- leaderboard with CIs
fo = defaultdict(int)
cby, gby = defaultdict(int), defaultdict(int)
for r in core["results"]:
    fo[r["adapter"]] += r["misreported_ok"]; cby[r["adapter"]] += r["complete"]
for r in gen["results"]:
    fo[r["adapter"]] += r["misreported_ok"]; gby[r["adapter"]] += r["complete"]
ci = an["bootstrap"]["ci"]
lines = []
for i, k in enumerate(t["order"], 1):
    r = t["rows"][k]
    c, f, n = r["stable"]
    s_c, _, s_n = r["stress"]
    lo, hi = ci[k]["lo"] * 100, ci[k]["hi"] * 100
    caps = " & ".join(f"{a}/{b}" for a, b in r["caps"])
    lines.append(f"{i} & \\texttt{{{k}}} & {pct(c, n)} {{\\scriptsize [{lo:.0f}, {hi:.0f}]}} & {pct(f, n)} & {caps} & "
                 f"{pct(s_c, s_n)} & {cby[k]}/44 & {gby[k]}/400 & {fo[k]} \\\\")
(G / "tab_leaderboard.tex").write_text("\n".join(lines) + "\n")
M("nSurfaces", str(len(t["order"])))

# ---------------------------------------------------------------- bootstrap separations
adj = an["bootstrap"]["adjacent"]
sig = [a for a in adj if a["p_higher"] >= 0.95]
M("nAdjSig", str(len(sig))); M("nAdj", str(len(adj)))
M("bootScenarios", num(an["bootstrap"]["n_scenarios"])); M("bootReps", num(an["bootstrap"]["reps"]))
M("adjSigList", ", ".join(f"\\texttt{{{a['higher']}}} $>$ \\texttt{{{a['lower']}}}" for a in sig))

# ---------------------------------------------------------------- ranking agreement
ag = an["agreement"]
M("tauCoreGen", f"{ag['core_vs_generated_stable']:.2f}")
seeds = sorted(k.split("_vs_")[1] for k in ag if k.startswith("seed1_vs_"))
M("nSeeds", str(1 + len(seeds)))
if seeds:
    taus = [ag[f"seed1_vs_{s}"] for s in seeds]
    pairs = [v for k, v in ag.items() if k.startswith("seed") and "_vs_seed" in k and not k.startswith("seed1_")]
    allt = taus + pairs
    M("tauSeedMin", f"{min(allt):.2f}"); M("tauSeedMax", f"{max(allt):.2f}")
    M("tauSeedMean", f"{sum(allt) / len(allt):.2f}")
    # per-seed stable rates table
    rates = {"seed1": ag["seed1_rates"]} | {s: ag[f"{s}_rates"] for s in seeds}
    rows = []
    for k in t["order"]:
        vals = [rates[s].get(k) for s in rates]
        rows.append(f"\\texttt{{{k}}} & " + " & ".join(f"{100 * v:.1f}" for v in vals) + " \\\\")
    (G / "tab_seeds.tex").write_text("\n".join(rows) + "\n")
    M("seedNames", ", ".join(s.replace("seed", "") for s in rates))

if seeds:
    (G / "seeds_sentence.tex").write_text(
        f"{len(seeds)} further suites with different seeds ($n{{=}}100$; seeds {', '.join(x.replace('seed', '') for x in seeds)}) "
        f"and ran them on all surfaces. Stable-tier rankings on the {len(seeds) + 1} independently generated suites agree with "
        f"Kendall $\\tau$ between {macros['tauSeedMin']} and {macros['tauSeedMax']} (mean {macros['tauSeedMean']}; "
        "Appendix~\\ref{app:seeds}), so the ranking is not an artifact of one sample of scenarios.\n")
    spread = max(max(rates[x][k] for x in rates) - min(rates[x][k] for x in rates) for k in t["order"])
    spread_k = max(t["order"], key=lambda k: max(rates[x][k] for x in rates) - min(rates[x][k] for x in rates))
    M("seedSpread", f"{100 * spread:.0f}")
    # do the top surface and the bottom three keep their places in every suite?
    def ranks(rt):
        return sorted(rt, key=lambda k: -rt[k])
    tops = {ranks(rates[x])[0] for x in rates}
    bottoms = {frozenset(ranks(rates[x])[-3:]) for x in rates}
    parts = []
    if len(tops) == 1:
        parts.append(f"\\texttt{{{next(iter(tops))}}} ranks first in every suite")
    if len(bottoms) == 1:
        parts.append("the same three surfaces (" + ", ".join(f"\\texttt{{{k}}}" for k in sorted(next(iter(bottoms))))
                     + ") occupy the last three places in every suite")
    ends_sentence = (" and ".join(parts) + ".") if parts else ""
    ends_sentence = ends_sentence[:1].upper() + ends_sentence[1:] if ends_sentence and not ends_sentence.startswith("\\") else ends_sentence
    (G / "seeds_appendix.tex").write_text(
        "Stable-tier completeness (\\%) per surface on independently generated suites: seed 1 ($n{=}200$, the released suite) "
        f"and seeds {', '.join(x.replace('seed', '') for x in seeds)} ($n{{=}}100$).\n\n"
        "\\begin{center}\\small\n\\begin{tabular}{l" + "c" * (len(seeds) + 1) + "}\n\\toprule\nSurface & "
        + " & ".join(f"Seed {x.replace('seed', '')}" for x in ["seed1"] + seeds)
        + " \\\\\n\\midrule\n\\inputtable{gen/tab_seeds.tex}\n\\bottomrule\n\\end{tabular}\n\\end{center}\n"
        + f"Individual rates move by up to {100 * spread:.0f} points between suites (largest for \\texttt{{{spread_k}}}), "
        "consistent with the bootstrap intervals in Figure~\\ref{fig:ci}. "
        + ends_sentence + "\n")
else:
    (G / "seeds_sentence.tex").write_text("\\todo{seed runs pending}.\n")
    (G / "seeds_appendix.tex").write_text("\\todo{seed runs pending}\n")

# ---------------------------------------------------------------- conditions
cond_rows = []
lg = an["conditions"]["logit"]
for c in an["conditions"]["conditions"]:
    coef = lg.get(c["key"])
    cond_rows.append(f"{c['label']} & {c['scenarios']} & {100 * c['with']:.1f} & {100 * c['without']:.1f} & "
                     + (f"${coef:+.2f}$" if coef is not None else "--") + " \\\\")
(G / "tab_conditions.tex").write_text("\n".join(cond_rows) + "\n")
M("logitCalls", f"{lg['log1p_calls']:.2f}".replace("-", "$-$"))
for k, nm in (("rejected", "Rej"), ("parallel", "Par"), ("cancelled", "Canc"), ("raising_tool", "Raise"), ("nested", "Nest")):
    M(f"logit{nm}", f"{lg[k]:.2f}".replace("-", "$-$"))
cv = an["conditions"]["curve"]
M("curveLo", f"{100 * cv['all'][0][1]:.0f}"); M("curveHi", f"{100 * cv['all'][-1][1]:.0f}")
M("smolLo", f"{100 * cv['smolagents/memory'][0][1]:.0f}"); M("smolHi", f"{100 * cv['smolagents/memory'][-1][1]:.0f}")

# ---------------------------------------------------------------- ablation
ab = an["ablation"]
M("ablIncomplete", num(ab["incomplete"])); M("ablCases", num(ab["cases"]))
M("ablRecallMiss", num(ab["recall_only_misses"])); M("ablRecallMissPct", pct(ab["recall_only_misses"], ab["incomplete"], 0))
M("ablRSMiss", num(ab["recall_status_misses"])); M("ablRSMissPct", pct(ab["recall_status_misses"], ab["incomplete"], 0))
bd = ab["by_defect"]; only = ab["only_reason"]
for k, name in [("missing_call", "Missing"), ("invisible_attempt", "Invisible"), ("false_success", "FalseOk"),
                ("status_mismatch", "Status")]:
    M(f"abl{name}", num(bd.get(k, 0))); M(f"abl{name}Only", num(only.get(k, 0)))

# ---------------------------------------------------------------- mutation table
descr = {k: v for k, v in DEFECTS.items()}
mrows = []
for d in DEFECTS:
    rows = mm[d]
    bad = [x for x in rows if not (x["complete"] and x["faithful"])]
    scn = sorted({x["scenario"] for x in bad})
    inc = any(not x["complete"] for x in bad)
    unf = any(not x["faithful"] for x in bad)
    axis = "C" if inc and not unf else "F" if unf and not inc else "C+F"
    gen_cell = "--"
    if mg:
        g = mg[d]
        gb = [x for x in g if not (x[2] and x[3])]
        gen_cell = f"{len(gb)}/{len(g)}"
    def compact(ids):
        nums = [int(s[1:]) for s in ids]
        out, i = [], 0
        while i < len(nums):
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                j += 1
            out.append(f"S{nums[i]:02d}" + (f"--S{nums[j]:02d}" if j > i else ""))
            i = j + 1
        return ", ".join(out)
    mrows.append(f"\\texttt{{{esc(d)}}} & {descr[d]} & {compact(scn)} & {axis} & {gen_cell} \\\\")
(G / "tab_mutation.tex").write_text("\n".join(mrows) + "\n")
M("refClean", "yes" if all(x["complete"] and x["faithful"] for x in mm["none"]) else "NO")
if mg:
    M("refCleanGen", "yes" if all(x[2] and x[3] for x in mg["none"]) else "NO")
    mins = min(sum(1 for x in mg[d] if not (x[2] and x[3])) for d in DEFECTS)
    M("mutGenMin", str(mins))

# ---------------------------------------------------------------- tasks
def fmt(v):
    return f"{v:.3f}".lstrip("0") if v < 1 else "1.000"


off = lb["official"]
trows = []
names = [("majority", "Majority class"), ("rules", "Rules (matching heuristics)"), ("logreg", "Logistic regression"),
         ("gbm", "Gradient-boosted trees")]
for key, lab in names:
    m = off[key]
    trows.append(f"{lab} & {fmt(m['T1_completeness']['defect_f1'])} & {fmt(m['T1_completeness']['balanced_accuracy'])} & "
                 f"{fmt(m['T2_fidelity']['defect_f1'])} & {fmt(m['T2_fidelity']['balanced_accuracy'])} & "
                 f"{fmt(m['T3_defects']['micro_f1'])} & {fmt(m['T3_defects']['macro_f1'])} & "
                 f"{fmt(m['T4_reconstruction']['call_accuracy'])} & {fmt(m['T4_reconstruction']['macro_f1'])} & "
                 f"{fmt(m['T4_reconstruction']['case_exact_match'])} \\\\")
m = lb["iid_gbm"]
trows.append("\\midrule\n\\textit{GBT, random split (frameworks seen)} & "
             f"{fmt(m['T1_completeness']['defect_f1'])} & {fmt(m['T1_completeness']['balanced_accuracy'])} & "
             f"{fmt(m['T2_fidelity']['defect_f1'])} & {fmt(m['T2_fidelity']['balanced_accuracy'])} & "
             f"{fmt(m['T3_defects']['micro_f1'])} & {fmt(m['T3_defects']['macro_f1'])} & "
             f"{fmt(m['T4_reconstruction']['call_accuracy'])} & {fmt(m['T4_reconstruction']['macro_f1'])} & "
             f"{fmt(m['T4_reconstruction']['case_exact_match'])} \\\\")
(G / "tab_tasks.tex").write_text("\n".join(trows) + "\n")
M("gbmTOneF", fmt(off["gbm"]["T1_completeness"]["defect_f1"]))
M("gbmTThreeMacro", fmt(off["gbm"]["T3_defects"]["macro_f1"]))
M("iidTThreeMacro", fmt(lb["iid_gbm"]["T3_defects"]["macro_f1"]))
M("gbmTFourExact", fmt(off["gbm"]["T4_reconstruction"]["case_exact_match"]))
M("iidTFourExact", fmt(lb["iid_gbm"]["T4_reconstruction"]["case_exact_match"]))
M("lrTThreeMacro", fmt(off["logreg"]["T3_defects"]["macro_f1"]))
M("lrTFourExact", fmt(off["logreg"]["T4_reconstruction"]["case_exact_match"]))

lrows = []
lo = lb["lofo"]
for fw, v in sorted(lo.items()):
    r, g = v["rules"], v["gbm"]
    lrows.append(f"\\texttt{{{fw}}} & {num(v['n'])} & {fmt(r['T1_completeness']['accuracy'])} & {fmt(g['T1_completeness']['accuracy'])} & "
                 f"{fmt(r['T4_reconstruction']['call_accuracy'])} & {fmt(g['T4_reconstruction']['call_accuracy'])} & "
                 f"{fmt(r['T4_reconstruction']['case_exact_match'])} & {fmt(g['T4_reconstruction']['case_exact_match'])} \\\\")
(G / "tab_lofo.tex").write_text("\n".join(lrows) + "\n")
worst = min(lo.items(), key=lambda kv: kv[1]["gbm"]["T4_reconstruction"]["case_exact_match"])
M("lofoWorstFw", worst[0]); M("lofoWorstExact", fmt(worst[1]["gbm"]["T4_reconstruction"]["case_exact_match"]))

ts = json.loads((ROOT / "hf-dataset/tasks/stats.json").read_text())
for s, nm in (("train", "Train"), ("validation", "Val"), ("test", "Test")):
    M(f"task{nm}N", num(ts[s]["examples"]))

# ---------------------------------------------------------------- cost
cst = an["cost"]
crow = [f"\\texttt{{{k}}} & {v['median_s']:.3f} & {v['total_min']:.1f} \\\\" for k, v in cst.items()]
(G / "tab_cost.tex").write_text("\n".join(crow) + "\n")
M("totalMinutes", f"{sum(v['total_min'] for v in cst.values()):.0f}")

# ---------------------------------------------------------------- history summary
hist = (ROOT / "results/HISTORY.md").read_text()
secs = re.split(r"^## ", hist, flags=re.M)[1:]
hrows = []
for sec in secs:
    name = sec.splitlines()[0].strip()
    vers = re.findall(r"^\| ([0-9][^|]*?) \| (\d{4}-\d\d-\d\d) \| (\d+)/44 \| (\d+)/44 \|", sec, re.M)
    if not vers:
        continue
    comp = [int(v[2]) for v in vers]
    dates = sorted(v[1] for v in vers)
    hrows.append(f"\\texttt{{{name}}} & {len(vers)} & {dates[0]} -- {dates[-1]} & {min(comp)}--{max(comp)} \\\\")
(G / "tab_history.tex").write_text("\n".join(hrows) + "\n")
alld = re.findall(r"^\| [0-9][^|]*? \| (\d{4}-\d\d-\d\d) \|", hist, re.M)
M("histFirst", min(alld)); M("histLast", max(alld))

# ---------------------------------------------------------------- scenarios appendix
srows = [f"{s.id} & {s.category} & {esc(s.title)} & {esc(s.description)} \\\\" for s in SCENARIOS]
(G / "tab_scenarios.tex").write_text("\n".join(srows) + "\n")

# ---------------------------------------------------------------- stability
unst = json.loads((ROOT / "results/generated/unstable_cases.json").read_text())
M("nUnstable", str(len(unst)))
M("stableAgree", num(len(gen["results"]) - len(unst)))
M("stableAgreePct", pct(len(gen["results"]) - len(unst), len(gen["results"])))


# ================================================================ v2 additions
gt = json.loads((A / "gt_ablation.json").read_text())
abl = gt["ablation_current"]
inc = abl["incomplete"]
comp_cases = abl["cases"] - inc
eo, lo_ = abl["emission_only"], abl["ledger_only"]
M("gtCases", num(abl["cases"])); M("gtIncomplete", num(inc)); M("gtComplete", num(comp_cases))
M("eoDetected", num(eo["detected"])); M("eoDetectedPct", pct(eo["detected"], inc))
M("eoFalse", num(eo["false_alarms"])); M("eoAmbig", num(eo["ambiguous_missing"]))
M("eoMissed", num(inc - eo["detected"]))
M("loDetected", num(lo_["detected"])); M("loDetectedPct", pct(lo_["detected"], inc))
M("loFalse", num(lo_["false_alarms"])); M("loFalsePct", pct(lo_["false_alarms"], comp_cases))
M("loMissed", num(inc - lo_["detected"]))
ll_ = abl["ledger_only_lenient"]
M("llDetected", num(ll_["detected"])); M("llDetectedPct", pct(ll_["detected"], inc)); M("llFalse", num(ll_["false_alarms"]))
(G / "tab_gt_ablation.tex").write_text(
    f"Emissions + ledger (TraceGap) & {num(inc)}/{num(inc)} & 0 & -- \\\\\n"
    f"Emission log only & {num(eo['detected'])}/{num(inc)} ({pct(eo['detected'], inc)}\\%) & {num(eo['false_alarms'])} & "
    f"status honesty: misses all {num(inc - eo['detected'])} cases whose only failure is a wrong status; cannot say whether a missing call ran \\\\\n"
    f"Ledger only, strict & {num(lo_['detected'])}/{num(inc)} ({pct(lo_['detected'], inc)}\\%) & {num(lo_['false_alarms'])} & "
    f"attempt visibility: misses {num(inc - lo_['detected'])} cases; correctly recorded rejected calls look like phantoms \\\\\n"
    f"Ledger only, lenient & {num(ll_['detected'])}/{num(inc)} ({pct(ll_['detected'], inc)}\\%) & {num(ll_['false_alarms'])} & "
    f"accepts unmatched records unless they claim success: few false alarms, misses {num(inc - ll_['detected'])} cases \\\\\n")

st = gt["stats_all"]; sc_ = st["counts"]; ls = st["ledger_status"]
cur = gt["stats_current"]["counts"]
rowsd = [
    ("Cases (current releases / past releases)", f"{num(sc_['cases'])} ({num(cur['cases'])} / {num(sc_['cases'] - cur['cases'])})"),
    ("Calibrated cases", num(sc_["calibrated"])),
    ("Frameworks / trace surfaces / releases", "9 / 15 / 65"),
    ("Emitted tool calls", num(sc_["emitted"])),
    ("Executed calls (ok / error / cancelled / still running)", f"{num(sc_['executed'])} ({num(ls.get('ok', 0))} / {num(ls.get('error', 0))} / {num(ls.get('cancelled', 0))} / {num(ls.get('running', 0))})"),
    ("Emitted but never executed (rejected or never reached)", num(sc_["never_executed"])),
    ("Recorded tool-call events", num(sc_["records"])),
    ("Stress-tier cases", num(sc_["stress"])),
    ("Incomplete cases", num(sc_["incomplete"])),
    ("Unfaithful cases", num(sc_["unfaithful"])),
    ("Calls recorded as successful that failed, were cancelled or never ran", num(sc_["false_success_calls"])),
    ("Duplicate records", num(sc_["duplicates"])),
]
(G / "tab_dataset.tex").write_text("\n".join(f"{a} & {b} \\\\" for a, b in rowsd) + "\n")
dl = st["defect_labels"]
from tracegap.tasks import DEFECTS as TDEF  # noqa: E402
(G / "tab_labels.tex").write_text("\n".join(f"\\texttt{{{esc(d)}}} & {num(dl.get(d, 0))} \\\\" for d in TDEF) + "\n")
M("dsEmitted", num(sc_["emitted"])); M("dsCases", num(sc_["cases"]))

# ---------------------------------------------------------------- learned models: all methods, seeds, LOFO summary
import numpy as _np  # noqa: E402

seqp = A / "sequence_baselines.json"
seq = json.loads(seqp.read_text()) if seqp.exists() else {}
KEYS = [("T1_completeness", "defect_f1"), ("T1_completeness", "balanced_accuracy"), ("T2_fidelity", "defect_f1"),
        ("T2_fidelity", "balanced_accuracy"), ("T3_defects", "micro_f1"), ("T3_defects", "macro_f1")]


def ms(vals):
    v = _np.array(vals)
    return (float(v.mean()), float(v.std()))


def cell(m, s=None):
    t = fmt(m)
    return t + (f"{{\\scriptsize$\\pm${s:.3f}".replace("0.", ".") + "}" if s is not None and s > 0 else "")


rows_all = []
for key, lab in [("majority", "Majority class"), ("rules", "Rules (matching heuristics)"),
                 ("logreg", "Logistic regression, features"), ("gbm", "Gradient-boosted trees, features")]:
    m = off[key]
    rows_all.append(lab + " & " + " & ".join(cell(m[t][k]) for t, k in KEYS) + " \\\\")
if "official" in seq:
    for key, lab in [("tfidf_lr", "TF-IDF + logistic regression"), ("transformer", "Transformer encoder (from scratch)")]:
        m = seq["official"][key]
        rows_all.append(lab + " & " + " & ".join(cell(m[f"{t}.{k}"]["mean"], m[f"{t}.{k}"]["std"]) for t, k in KEYS) + " \\\\")
(G / "tab_tasks_all.tex").write_text("\n".join(rows_all) + "\n")

# which frameworks have positives for each task (LOFO metrics are undefined otherwise)
import pyarrow.parquet as _pq  # noqa: E402

_task_rows = []
for _sp in ("train", "validation", "test"):
    _task_rows += _pq.read_table(ROOT / "hf-dataset/tasks" / f"{_sp}.parquet",
                                 columns=["framework", "label_complete", "label_faithful", "label_defects"]).to_pylist()
HAS = {"T1": {r["framework"] for r in _task_rows if not r["label_complete"]},
       "T2": {r["framework"] for r in _task_rows if not r["label_faithful"]},
       "T3": {r["framework"] for r in _task_rows if r["label_defects"]}}
GEN = [("T1", "T1_completeness", "defect_f1"), ("T2", "T2_fidelity", "defect_f1"), ("T3", "T3_defects", "macro_f1")]


def lofo_feat(key, t, k, tag):
    return [lb["lofo"][fw][key][t][k] for fw in lb["lofo"] if fw in HAS[tag]]


def lofo_seq(key, t, k, tag):
    return [seq["lofo"][fw][key][f"{t}.{k}"]["mean"] for fw in seq.get("lofo", {}) if fw in HAS[tag]]


split_rows = []
for key, lab in [("logreg", "LR, features"), ("gbm", "GBT, features")]:
    cells = []
    for tag, t, k in GEN:
        r_m, r_s = ms([x[t][k] for x in lb["iid_runs"][key]])
        l_m, l_s = ms(lofo_feat(key, t, k, tag))
        cells.append(f"{cell(r_m, r_s)} & {cell(off[key][t][k])} & {cell(l_m, l_s)}")
    split_rows.append(f"{lab} & " + " & ".join(cells) + " \\\\")
for key, lab in [("tfidf_lr", "TF-IDF + LR"), ("transformer", "Transformer")]:
    if not all(x in seq for x in ("random", "official", "lofo")):
        continue
    cells = []
    for tag, t, k in GEN:
        r = seq["random"][key][f"{t}.{k}"]
        h = seq["official"][key][f"{t}.{k}"]
        l_m, l_s = ms(lofo_seq(key, t, k, tag))
        cells.append(f"{cell(r['mean'], r['std'])} & {cell(h['mean'], h['std'])} & {cell(l_m, l_s)}")
    split_rows.append(f"{lab} & " + " & ".join(cells) + " \\\\")
(G / "tab_splits.tex").write_text("\n".join(split_rows) + "\n")
if all(x in seq for x in ("random", "official", "lofo")):
    M("seqTOneRandom", fmt(seq["random"]["transformer"]["T1_completeness.defect_f1"]["mean"]))
    M("seqTOneHeld", fmt(seq["official"]["transformer"]["T1_completeness.defect_f1"]["mean"]))
    M("seqTThreeRandom", fmt(seq["random"]["transformer"]["T3_defects.macro_f1"]["mean"]))
    M("seqTThreeHeld", fmt(seq["official"]["transformer"]["T3_defects.macro_f1"]["mean"]))
    M("seqTThreeLofo", fmt(ms(lofo_seq("transformer", "T3_defects", "macro_f1", "T3"))[0]))
    M("tfTThreeRandom", fmt(seq["random"]["tfidf_lr"]["T3_defects.macro_f1"]["mean"]))
    M("tfTThreeHeld", fmt(seq["official"]["tfidf_lr"]["T3_defects.macro_f1"]["mean"]))
for key, nm in (("gbm", "Gbm"), ("logreg", "Lr")):
    M(f"iid{nm}TThreeMean", fmt(ms([x["T3_defects"]["macro_f1"] for x in lb["iid_runs"][key]])[0]))
    M(f"lofo{nm}TThreeMean", fmt(ms(lofo_feat(key, "T3_defects", "macro_f1", "T3"))[0]))
    M(f"lofo{nm}TOneMean", fmt(ms(lofo_feat(key, "T1_completeness", "defect_f1", "T1"))[0]))
    M(f"iid{nm}TOneMean", fmt(ms([x["T1_completeness"]["defect_f1"] for x in lb["iid_runs"][key]])[0]))

# LOFO per framework: T1 F1 and T3 macro F1 for every method
lrows2 = []
for fw in sorted(lb["lofo"]):
    v = lb["lofo"][fw]
    def g(tag, t, k):
        if fw not in HAS[tag]:
            return ["--"] * 5
        out = [fmt(v["rules"][t][k]), fmt(v["logreg"][t][k]), fmt(v["gbm"][t][k])]
        if "lofo" in seq and fw in seq["lofo"]:
            out += [fmt(seq["lofo"][fw]["tfidf_lr"][f"{t}.{k}"]["mean"]), fmt(seq["lofo"][fw]["transformer"][f"{t}.{k}"]["mean"])]
        else:
            out += ["", ""]
        return out
    lrows2.append(f"\\texttt{{{fw}}} & {num(v['n'])} & " + " & ".join(g("T1", "T1_completeness", "defect_f1") + g("T3", "T3_defects", "macro_f1")) + " \\\\")
(G / "tab_lofo_t13.tex").write_text("\n".join(lrows2) + "\n")
print("v2 tables written")

(G / "numbers.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items())))

# T4 table (feature models)
t4rows = []
for key, lab in [("majority", "Majority class"), ("rules", "Rules"), ("logreg", "Logistic regression, features"),
                 ("gbm", "Gradient-boosted trees, features")]:
    m = off[key]["T4_reconstruction"]
    t4rows.append(f"{lab} & {fmt(m['call_accuracy'])} & {fmt(m['macro_f1'])} & {fmt(m['case_exact_match'])} \\\\")
r4 = lb["iid_runs"]["gbm"]
def _ms4(k):
    mm, ss = ms([x["T4_reconstruction"][k] for x in r4])
    return cell(mm, ss)
t4rows.append("\\midrule\n\\textit{GBT, random split (frameworks seen)} & " + " & ".join(_ms4(k) for k in ("call_accuracy", "macro_f1", "case_exact_match")) + " \\\\")
(G / "tab_t4.tex").write_text("\n".join(t4rows) + "\n")
M("iidTFourExact", fmt(ms([x["T4_reconstruction"]["case_exact_match"] for x in r4])[0]))
(G / "numbers.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items())))

# drops from random split to LOFO mean, all learned methods x T1-T3 F1 metrics
drops, sds = [], []
for key in ("logreg", "gbm"):
    for tag, t, k in GEN:
        r = ms([x[t][k] for x in lb["iid_runs"][key]])[0]
        lm, lsd = ms(lofo_feat(key, t, k, tag))
        drops.append(r - lm); sds.append(lsd)
if all(x in seq for x in ("random", "official", "lofo")):
    for key in ("tfidf_lr", "transformer"):
        for tag, t, k in GEN:
            r = seq["random"][key][f"{t}.{k}"]["mean"]
            lm, lsd = ms(lofo_seq(key, t, k, tag))
            drops.append(r - lm); sds.append(lsd)
M("dropMin", fmt(min(drops))); M("dropMax", fmt(max(drops))); M("lofoSdMax", fmt(max(sds)))
M("allDropsPositive", "yes" if all(d > 0 for d in drops) else "NO")
(G / "numbers.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items())))


# ================================================================ v3: feature ablation, surface probe, tag masking
fap = A / "feature_ablation.json"
if True:
    fa = json.loads(fap.read_text())
    frows = []
    for r in fa["cumulative"]:
        o, l = r["gbm_official"], r["gbm_lofo"]
        lo = r["logreg_official"]
        frows.append(f"{r['label']} & {r['n_features']} & {fmt(o['T1'])} & {fmt(o['T2'])} & {fmt(o['T3'])} & "
                     f"{cell(l['T1']['mean'], l['T1']['std'])} & {cell(l['T2']['mean'], l['T2']['std'])} & "
                     f"{cell(l['T3']['mean'], l['T3']['std'])} & {fmt(lo['T1'])} & {fmt(lo['T3'])} \\\\")
    (G / "tab_feat_ablation.tex").write_text("\n".join(frows) + "\n")
    c0, c4, c5 = fa["cumulative"][0], fa["cumulative"][4], fa["cumulative"][5]
    M("faCountsTOne", fmt(c0["gbm_official"]["T1"])); M("faCountsTOneLofo", fmt(c0["gbm_lofo"]["T1"]["mean"]))
    M("faNoRatesTOne", fmt(c4["gbm_official"]["T1"])); M("faNoRatesTOneLofo", fmt(c4["gbm_lofo"]["T1"]["mean"]))
    M("faNoRatesTTwo", fmt(c4["gbm_official"]["T2"])); M("faNoRatesTThree", fmt(c4["gbm_official"]["T3"]))
    M("faNoRatesTThreeLofo", fmt(c4["gbm_lofo"]["T3"]["mean"]))
    M("faAllTOne", fmt(c5["gbm_official"]["T1"])); M("faAllTThree", fmt(c5["gbm_official"]["T3"]))
    M("faAllTOneLofo", fmt(c5["gbm_lofo"]["T1"]["mean"])); M("faAllTThreeLofo", fmt(c5["gbm_lofo"]["T3"]["mean"]))
    M("faNoMissingTTwo", fmt(fa["cumulative"][3]["gbm_official"]["T2"]))
    M("faWithMissingTTwo", fmt(c4["gbm_official"]["T2"]))
    pr = fa["probe"]
    M("probeAll", pct(pr["all"]["mean"], 1)); M("probeNoRates", pct(pr["without_rates"]["mean"], 1))
    M("probeCounts", pct(pr["counts_only"]["mean"], 1)); M("probeChance", pct(pr["chance"], 1))
    M("probeClasses", str(pr["n_classes"]))

tg = A / "learned_baselines_tagged.json"
if True:
    lt = json.loads(tg.read_text())
    lb_all = json.loads((A / "learned_baselines_allfeatures.json").read_text())  # same 26 features, masked
    trow = []
    for key, lab in (("rules", "Rules"), ("logreg", "LR, features"), ("gbm", "GBT, features")):
        def four(m):
            return [m["T1_completeness"]["defect_f1"], m["T2_fidelity"]["defect_f1"], m["T3_defects"]["macro_f1"],
                    m["T4_reconstruction"]["case_exact_match"]]
        a, b = four(lt["official"][key]), four(lb_all["official"][key])
        def lofo_mean(src, k2, idx):
            vals = []
            tag = ["T1", "T2", "T3", None][idx]
            for fw, v in src["lofo"].items():
                if tag and fw not in HAS[tag]:
                    continue
                vals.append(four(v[k2])[idx])
            return float(_np.mean(vals))
        la = [lofo_mean(lt, key, i) for i in range(4)]
        lbm = [lofo_mean(lb_all, key, i) for i in range(4)]
        trow.append(f"{lab} & " + " & ".join(f"{fmt(x)} $\\rightarrow$ {fmt(y)}" for x, y in zip(a, b)) + " & "
                    + " & ".join(f"{fmt(x)} $\\rightarrow$ {fmt(y)}" for x, y in zip(la[:1] + la[2:3], lbm[:1] + lbm[2:3])) + " \\\\")
    (G / "tab_tag.tex").write_text("\n".join(trow) + "\n")
    diffs = []
    for key in ("logreg", "gbm"):  # feature models only
        for t, k in (("T1_completeness", "defect_f1"), ("T2_fidelity", "defect_f1"), ("T3_defects", "macro_f1"),
                     ("T4_reconstruction", "case_exact_match")):
            diffs.append(abs(lt["official"][key][t][k] - lb_all["official"][key][t][k]))
    M("tagMaxDiff", fmt(max(diffs)))
    ldiffs = [abs(lofo_mean(lt, key, i) - lofo_mean(lb_all, key, i)) for key in ("logreg", "gbm") for i in range(4)]
    M("tagMaxDiffLofo", fmt(max(ldiffs)))

(G / "numbers.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items())))
print(f"wrote {len(macros)} macros and tables to {G}")
