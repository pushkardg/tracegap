"""Feature-based baselines (logistic regression, gradient-boosted trees) for TraceGap tasks T1-T4.

Features are computed only from task inputs (emitted calls, recorded trace,
run outcome); the ledger and labels are never used. Three settings:
  1. the official split (train -> test, frameworks held out);
  2. random 80/20 splits (5 seeds; every framework seen in training);
  3. leave-one-framework-out (LOFO) over all nine frameworks.

    python analysis/learned_baselines.py                       # reference: 24 surface-agnostic features
    python analysis/learned_baselines.py --features all \
        --out analysis/out/learned_baselines_allfeatures.json --skip-iid      # 26 features (tag ablation)
    python -m tracegap.tasks build --keep-tag --out analysis/out/tasks_tagged
    python analysis/learned_baselines.py --features all --tasks analysis/out/tasks_tagged \
        --out analysis/out/learned_baselines_tagged.json --skip-iid           # unmasked inputs (tag ablation)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from tracegap import tasks  # noqa: E402
from tracegap.adapters.reference import _validate  # noqa: E402
from tracegap.tools import TOOLS  # noqa: E402

TD = ROOT / "hf-dataset" / "tasks"
FEATURE_SET = "agnostic"  # or "all"; set from the command line
OUT = ROOT / "analysis" / "out"
OUTCOMES = ["completed", "cancelled", "raised"]


def valid_call(e) -> bool:
    fn = TOOLS.get(e["name"])
    if fn is None:
        return False
    args = dict(e["args"] or {})
    args.setdefault("tag", "t")  # the harness tag is masked from task inputs; every call carried one
    try:
        _validate(fn, args)
        return True
    except TypeError:
        return False


def match(em, rec):
    matches, unmatched = tasks._match(em, rec)
    return matches, unmatched


SURFACE_FEATURES = (16, 17)  # capture rates of args and call ids: characterize a surface (see feature_ablation.py)


def case_features(ex):
    """The 24 surface-agnostic features (reference baselines), or all 26 with --features all."""
    f = case_features_full(ex)
    return f if FEATURE_SET == "all" else np.delete(f, SURFACE_FEATURES)


def case_features_full(ex):
    """All 26 features, including the two surface-characterizing capture rates."""
    em = json.loads(ex["emissions_json"])
    rec = json.loads(ex["recorded_json"])
    matches, unmatched = match(em, rec)
    st = Counter(r["status"] for r in rec)
    n_em, n_rec = len(em), len(rec)
    matched = sum(1 for m in matches if m)
    multi = sum(1 for m in matches if len(m) > 1)
    invalid = sum(1 for e in em if not valid_call(e))
    invalid_unmatched = sum(1 for e, m in zip(em, matches) if not m and not valid_call(e))
    valid_unmatched = sum(1 for e, m in zip(em, matches) if not m and valid_call(e))
    ok_no_out = sum(1 for r in rec if r["status"] == "ok" and r.get("output") is None)
    err_no_msg = sum(1 for r in rec if r["status"] == "error" and not r.get("error"))
    args_none = sum(1 for r in rec if r.get("args") is None)
    id_none = sum(1 for r in rec if not r.get("call_id"))
    groups = len({r.get("group") for r in rec})
    runs = len({e["run_index"] for e in em})
    oc = ex["run_outcome"]
    f = [n_em, n_rec, n_rec - n_em, matched / max(1, n_em), n_em - matched, multi, len(unmatched),
         st["ok"], st["error"], st["incomplete"], st["unknown"], invalid, invalid_unmatched, valid_unmatched,
         ok_no_out, err_no_msg, args_none / max(1, n_rec), id_none / max(1, n_rec), groups, runs,
         float(groups > runs), sum(1 for e in em if e.get("nested")),
         float(ex["mode"] == "stream")] + [float(o in oc) for o in OUTCOMES]
    return np.array(f, dtype=float)


def call_features(ex):
    em = json.loads(ex["emissions_json"])
    rec = json.loads(ex["recorded_json"])
    matches, _ = match(em, rec)
    oc = ex["run_outcome"]
    caseagg = case_features(ex)
    rows = []
    n = len(em)
    # position of last matched emission within each run (later calls after it may not have run)
    last_matched = {}
    for i, (e, m) in enumerate(zip(em, matches)):
        if m:
            last_matched[e["run_index"]] = i
    for i, (e, m) in enumerate(zip(em, matches)):
        r = m[-1] if m else None
        status = r["status"] if r else "none"
        rows.append(np.concatenate([[
            float(bool(m)), len(m), float(status == "ok"), float(status == "error"), float(status == "incomplete"),
            float(status == "unknown"), float(r is not None and r.get("output") is None),
            float(r is not None and bool(r.get("error"))), float(valid_call(e)), float(bool(e.get("nested"))),
            i / max(1, n - 1), float(i > last_matched.get(e["run_index"], -1)), float(i == n - 1),
        ] + [float(o in oc) for o in OUTCOMES], caseagg]))
    return rows


def load_all():
    rows = []
    for s in ("train", "validation", "test"):
        rows += tasks.load(TD, s)
    return rows


def split_of(fw):
    return next(s for s, fws in tasks.SPLITS.items() if fw in fws)


def fit_binary(X, y):
    if len(set(y)) < 2:
        const = y[0]
        return lambda Z: np.full(len(Z), const)
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0).fit(X, y)
    return m.predict


def fit_logreg(X, y):
    if len(set(y)) < 2:
        const = y[0]
        return lambda Z: np.full(len(Z), const)
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")).fit(X, y)
    return m.predict


def run(train, test, kind="gbm"):
    fit = fit_binary if kind == "gbm" else fit_logreg
    Xtr = np.stack([case_features(e) for e in train])
    Xte = np.stack([case_features(e) for e in test])
    preds = {e["id"]: {} for e in test}
    for key, lab in (("complete", "label_complete"), ("faithful", "label_faithful")):
        p = fit(Xtr, np.array([e[lab] for e in train]))(Xte)
        for e, v in zip(test, p):
            preds[e["id"]][key] = bool(v)
    # T3: one model per defect label
    lab_sets = [set(e["label_defects"]) for e in train]
    dpred = {e["id"]: [] for e in test}
    for d in tasks.DEFECTS:
        y = np.array([d in s for s in lab_sets])
        p = fit(Xtr, y)(Xte)
        for e, v in zip(test, p):
            if v:
                dpred[e["id"]].append(d)
    for e in test:
        preds[e["id"]]["defects"] = dpred[e["id"]]
    # T4: per-call classifier
    Ctr = [(f, s) for e in train for f, s in zip(call_features(e), e["label_call_status"])]
    Xc = np.stack([f for f, _ in Ctr])
    yc = np.array([s for _, s in Ctr])
    if kind == "gbm":
        cm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0).fit(Xc, yc)
    else:
        cm = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")).fit(Xc, yc)
    for e in test:
        fs = call_features(e)
        preds[e["id"]]["call_status"] = list(cm.predict(np.stack(fs))) if fs else []
    return preds


def main():
    global FEATURE_SET, TD
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", choices=["agnostic", "all"], default="agnostic")
    ap.add_argument("--tasks", default=str(TD))
    ap.add_argument("--out", default=str(OUT / "learned_baselines.json"))
    ap.add_argument("--skip-iid", action="store_true")
    a = ap.parse_args()
    FEATURE_SET, TD = a.features, Path(a.tasks)
    allx = load_all()
    res = {}
    train = [e for e in allx if split_of(e["framework"]) == "train"]
    test = [e for e in allx if split_of(e["framework"]) == "test"]
    maj = tasks.majority(train)
    res["official"] = {
        "majority": tasks.evaluate(test, {e["id"]: maj(e) for e in test}),
        "rules": tasks.evaluate(test, {e["id"]: tasks.heuristic(e) for e in test}),
        "logreg": tasks.evaluate(test, run(train, test, "logreg")),
        "gbm": tasks.evaluate(test, run(train, test, "gbm")),
    }
    # in-distribution reference: random 80/20 splits (frameworks seen in training), 5 split seeds
    iid = {"gbm": [], "logreg": []}
    for seed in ([] if a.skip_iid else range(5)):
        rng = np.random.default_rng(100 + seed)
        perm = rng.permutation(len(allx))
        cut = int(0.8 * len(allx))
        tr_iid = [allx[i] for i in perm[:cut]]
        te_iid = [allx[i] for i in perm[cut:]]
        for kind in iid:
            iid[kind].append(tasks.evaluate(te_iid, run(tr_iid, te_iid, kind)))
        print("iid seed", seed, flush=True)
    res["iid_runs"] = iid
    res["iid_gbm"] = iid["gbm"][0] if iid["gbm"] else None
    res["config"] = {"features": FEATURE_SET, "tasks": str(TD)}
    # leave one framework out
    lofo = {}
    for fw in sorted({e["framework"] for e in allx}):
        tr = [e for e in allx if e["framework"] != fw]
        te = [e for e in allx if e["framework"] == fw]
        r_rules = tasks.evaluate(te, {e["id"]: tasks.heuristic(e) for e in te})
        r_gbm = tasks.evaluate(te, run(tr, te, "gbm"))
        r_lr = tasks.evaluate(te, run(tr, te, "logreg"))
        lofo[fw] = {"n": len(te), "rules": r_rules, "gbm": r_gbm, "logreg": r_lr}
        print(fw, len(te), round(r_rules["T1_completeness"]["balanced_accuracy"], 3),
              round(r_gbm["T1_completeness"]["balanced_accuracy"], 3),
              round(r_rules["T4_reconstruction"]["call_accuracy"], 3), round(r_gbm["T4_reconstruction"]["call_accuracy"], 3),
              flush=True)
    res["lofo"] = lofo
    OUT.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    for k in ("official",):
        for name, m in res[k].items():
            print(k, name, {t: {kk: round(vv, 3) for kk, vv in v.items()} for t, v in m.items()})
    if res["iid_gbm"]:
        print("iid", {t: {kk: round(vv, 3) for kk, vv in v.items()} for t, v in res["iid_gbm"].items()})


if __name__ == "__main__":
    main()
