"""Feature ablation for the feature-based baselines, and a surface-identification probe.

1. Cumulative feature groups for gradient-boosted trees (and logistic
   regression), on the official held-out split and leave-one-framework-out:
   counts and structure -> + recorded statuses -> + schema validity ->
   + run outcome and mode -> + missing outputs/errors -> + captured-field
   rates (= all 26 features). The row before the last is the model without
   the features that characterize a surface's conventions.
2. Probe: how well do the features identify the trace surface (15 classes)?
   A high score means a model could memorize per-surface failure modes.

    python analysis/feature_ablation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

import learned_baselines as LB  # noqa: E402
from tracegap import tasks  # noqa: E402

GROUPS = [
    ("counts", "Counts and structure", [0, 1, 2, 3, 4, 5, 6, 18, 19, 20, 21]),
    ("status", "+ recorded statuses", [7, 8, 9, 10]),
    ("schema", "+ schema validity", [11, 12, 13]),
    ("outcome", "+ run outcome and mode", [22, 23, 24, 25]),
    ("missing", "+ missing outputs and errors", [14, 15]),
    ("rates", "+ captured-field rates (all)", list(LB.SURFACE_FEATURES)),
]
_orig_case = LB.case_features_full


def use(cols):
    LB.case_features = (lambda ex, _c=np.array(cols): _orig_case(ex)[_c]) if cols is not None else _orig_case


def evaluate(train, test, kind):
    m = tasks.evaluate(test, LB.run(train, test, kind))
    return {"T1": m["T1_completeness"]["defect_f1"], "T2": m["T2_fidelity"]["defect_f1"],
            "T3": m["T3_defects"]["macro_f1"], "T4": m["T4_reconstruction"]["case_exact_match"]}


def has_pos(rows):
    return {"T1": any(not e["label_complete"] for e in rows), "T2": any(not e["label_faithful"] for e in rows),
            "T3": any(e["label_defects"] for e in rows), "T4": True}


def main():
    allx = LB.load_all()
    train = [e for e in allx if LB.split_of(e["framework"]) == "train"]
    test = [e for e in allx if LB.split_of(e["framework"]) == "test"]
    fws = sorted({e["framework"] for e in allx})
    out = {"cumulative": [], "probe": {}}
    cols = []
    for key, label, idx in GROUPS:
        cols = cols + idx
        row = {"key": key, "label": label, "n_features": len(cols)}
        use(cols)
        for kind in ("gbm", "logreg"):
            row[f"{kind}_official"] = evaluate(train, test, kind)
        # LOFO for GBT (mean over frameworks with positives for each task)
        per = {}
        for fw in fws:
            tr = [e for e in allx if e["framework"] != fw]
            te = [e for e in allx if e["framework"] == fw]
            per[fw] = (evaluate(tr, te, "gbm"), has_pos(te))
        lofo = {}
        for t in ("T1", "T2", "T3", "T4"):
            v = [r[t] for r, hp in per.values() if hp[t]]
            lofo[t] = {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
        row["gbm_lofo"] = lofo
        row["gbm_lofo_per_fw"] = {fw: r for fw, (r, _) in per.items()}
        out["cumulative"].append(row)
        print(label, {k: round(v, 3) for k, v in row["gbm_official"].items()},
              {t: round(v["mean"], 3) for t, v in lofo.items()}, flush=True)
    use(None)

    # surface-identification probe: 5-fold grouped by scenario, so no scenario appears in both train and test
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    y = np.array([f"{e['framework']}/{e['surface']}" for e in allx])
    groups = np.array([e["id"].split("/")[5] for e in allx])  # scenario id
    full = np.stack([_orig_case(e) for e in allx])
    no_rates = np.delete(full, list(LB.SURFACE_FEATURES), axis=1)
    counts_only = full[:, GROUPS[0][2]]
    for name, X in (("all", full), ("without_rates", no_rates), ("counts_only", counts_only)):
        accs = []
        for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
            m = HistGradientBoostingClassifier(max_iter=200, random_state=0).fit(X[tr], y[tr])
            accs.append(float((m.predict(X[te]) == y[te]).mean()))
        out["probe"][name] = {"mean": float(np.mean(accs)), "std": float(np.std(accs))}
    out["probe"]["chance"] = float(max(np.mean(y == c) for c in set(y)))
    out["probe"]["n_classes"] = len(set(y))
    print("probe", out["probe"])
    (LB.OUT / "feature_ablation.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
