"""Machine-learning tasks over the TraceGap corpus.

Every row of the corpus pairs what a framework *recorded* with what really
happened (the execution ledger written by the tools). The tasks below hide the
ledger and ask a method to recover facts about it from information a real
observability pipeline would have: the calls the model emitted, the trace the
framework recorded, and the run's outcome.

  T1  completeness detection   is the recorded trace complete?        (binary)
  T2  fidelity detection       are recorded args/outputs/errors exact? (binary)
  T3  defect classification    which defect types are present?          (multi-label)
  T4  execution reconstruction for each emitted call, what really happened?
                               ok | error | cancelled | running | not_executed
  T5  trace normalization      turn a framework's native trace into the
                               canonical record. Scored by the benchmark itself:
                               write an adapter and run `python -m tracegap.check_adapter`.

Inputs per example (fields of the task Parquet files):
  framework, surface, framework_version, mode, suite, tier, run_outcome,
  emissions_json   calls the model emitted (call_id, name, args, run_index, nested)
  recorded_json    the framework's trace, normalized (name, args, status,
                   output, error, call_id, group, order)
  In both, the harness's unique ``tag`` argument is removed from args, since
  production tools have none; match calls by call id.

Labels: label_complete, label_faithful, label_defects, label_call_status.

Splits hold out whole frameworks so methods must generalize to an unseen
framework's trace conventions:
  train       langgraph, pydantic-ai, autogen, llamaindex, crewai
  validation  openai-agents, semantic-kernel
  test        google-adk, smolagents

Commands:
  python -m tracegap.tasks build     [--data hf-dataset/data] [--out hf-dataset/tasks]
  python -m tracegap.tasks baselines [--tasks hf-dataset/tasks] [--split test]
  python -m tracegap.tasks evaluate  PREDICTIONS.jsonl [--split test]

A predictions file has one JSON object per line with "id" and any of
"complete" (bool), "faithful" (bool), "defects" (list[str]) and
"call_status" (list[str], aligned with emissions order).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

SPLITS = {
    "train": {"langgraph", "pydantic-ai", "autogen", "llamaindex", "crewai"},
    "validation": {"openai-agents", "semantic-kernel"},
    "test": {"google-adk", "smolagents"},
}

DEFECTS = [
    "missing_call",        # a call that executed is absent from the trace
    "invisible_attempt",   # an emitted call that never ran left no trace
    "false_success",       # a failed, cancelled or never-run call is recorded as successful
    "status_mismatch",     # any other wrong status (e.g. ok recorded as incomplete)
    "duplicate",           # recorded more times than executed
    "phantom",             # trace has a call the model never emitted, or one that cannot be attributed
    "isolation",           # one run split across groups, or runs mixed in one group
    "args_lost",           # recorded arguments differ from the real ones
    "output_lost",         # recorded output missing, truncated or different
    "error_lost",          # error message not recorded
]

STATUSES = ["ok", "error", "cancelled", "running", "not_executed"]


def defects_from(failures: list[str], fidelity_failures: list[str]) -> list[str]:
    """Map the scorer's failure reasons to defect labels."""
    out = set()
    for f in failures:
        if "but missing from trace" in f:
            out.add("missing_call")
        elif "emitted but never executed, and the attempt is invisible" in f:
            out.add("invisible_attempt")
        elif "never executed but trace reports success" in f or (
            "but trace status=ok" in f and "actual=ok" not in f
        ):
            out.add("false_success")
        elif "but trace status=" in f:
            out.add("status_mismatch")
        elif "recorded" in f and "times" in f:
            out.add("duplicate")
        elif f.startswith("phantom") or f.startswith("unattributable"):
            out.add("phantom")
        elif "split across" in f or "mixes calls" in f:
            out.add("isolation")
        elif f.startswith("harness error"):
            pass
        else:
            raise ValueError(f"unmapped failure reason: {f}")
    for f in fidelity_failures:
        if "args differ" in f:
            out.add("args_lost")
        elif ": output " in f:
            out.add("output_lost")
        elif "error message not recorded" in f:
            out.add("error_lost")
        else:
            raise ValueError(f"unmapped fidelity reason: {f}")
    return [d for d in DEFECTS if d in out]


def call_status(emissions: list[dict], ledger: list[dict]) -> list[str]:
    by_tag: dict[str, str] = {}
    for le in ledger:
        by_tag.setdefault(le["tag"], le["status"])
    return [by_tag.get(e["tag"], "not_executed") for e in emissions]


def _mask_args(args):
    if isinstance(args, dict):
        return {k: v for k, v in args.items() if k != "tag"}
    return args


def strip_emissions(emissions: list[dict], keep_tag: bool = False) -> list[dict]:
    """Remove the harness-only 'tag' key and (unless keep_tag) the tag argument.
    Production tools have no such argument, so it must not help a method match
    calls; the call id is the realistic join key."""
    return [{k: (v if keep_tag or k != "args" else _mask_args(v)) for k, v in e.items() if k != "tag"}
            for e in emissions]


def _scrub(value, tags: set[str]):
    """Remove tag values from recorded outputs and error messages (some tools echo their tag)."""
    if isinstance(value, dict):
        return {k: _scrub(v, tags) for k, v in value.items() if k != "tag"}
    if isinstance(value, list):
        return [_scrub(v, tags) for v in value]
    if isinstance(value, str) and tags:
        alts = [re.escape(t) for t in sorted(tags, key=len, reverse=True)]
        return re.sub(r"\b(" + "|".join(alts) + r")\b", "<tag>", value)
    return value


def strip_recorded(recorded: list[dict], tags: set[str] = frozenset(), keep_tag: bool = False) -> list[dict]:
    if keep_tag:
        return recorded
    out = []
    for r in recorded:
        r = dict(r)
        if "args" in r:
            r["args"] = _mask_args(r["args"])
        for k in ("output", "error"):
            if k in r:
                r[k] = _scrub(r[k], tags)
        out.append(r)
    return out


# ---------------------------------------------------------------- build

def build(data_dir: Path, out_dir: Path, keep_tag: bool = False) -> dict:
    """keep_tag=True keeps the harness tag in inputs (used only for the masking ablation)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    split_of = {fw: s for s, fws in SPLITS.items() for fw in fws}
    rows = {s: [] for s in SPLITS}
    for f in sorted(data_dir.glob("*.parquet")):
        for r in pq.read_table(f).to_pylist():
            if not r["calibrated"] or r["harness_error"]:
                continue
            em = json.loads(r["emissions_json"])
            led = json.loads(r["ledger_json"])
            ex = {
                "id": f"{r['split']}/{r['suite']}/{r['framework']}/{r['surface']}/"
                      f"{r['framework_version'].split(',')[0].split()[-1]}/{r['scenario_id']}/{r['mode']}",
                "framework": r["framework"],
                "surface": r["surface"],
                "framework_version": r["framework_version"],
                "mode": r["mode"],
                "suite": r["suite"],
                "source_split": r["split"],
                "tier": r["tier"],
                "run_outcome": r["run_outcome"],
                "emissions_json": json.dumps(strip_emissions(em, keep_tag)),
                "recorded_json": json.dumps(strip_recorded(json.loads(r["recorded_json"]),
                                                           {e["tag"] for e in em if e.get("tag")}
                                                           | {x["tag"] for x in led if x.get("tag")}, keep_tag)),
                "label_complete": r["complete"],
                "label_faithful": r["faithful"],
                "label_defects": defects_from(r["failures"], r["fidelity_failures"]),
                "label_call_status": call_status(em, led),
            }
            rows[split_of[r["framework"]]].append(ex)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for s, rs in rows.items():
        ids = [x["id"] for x in rs]
        assert len(ids) == len(set(ids)), f"duplicate ids in {s}"
        pq.write_table(pa.Table.from_pylist(rs), out_dir / f"{s}.parquet")
        stats[s] = {
            "examples": len(rs),
            "frameworks": sorted({x["framework"] for x in rs}),
            "complete": sum(x["label_complete"] for x in rs),
            "faithful": sum(x["label_faithful"] for x in rs),
            "calls": sum(len(x["label_call_status"]) for x in rs),
            "defects": dict(Counter(d for x in rs for d in x["label_defects"])),
            "call_status": dict(Counter(c for x in rs for c in x["label_call_status"])),
        }
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def load(tasks_dir: Path, split: str) -> list[dict]:
    import pyarrow.parquet as pq

    return pq.read_table(tasks_dir / f"{split}.parquet").to_pylist()


# ---------------------------------------------------------------- metrics

def _binary(gold: list[bool], pred: list[bool]) -> dict:
    """Positive class = the defect (incomplete / unfaithful), since detecting
    defects is the point."""
    tp = sum(1 for g, p in zip(gold, pred) if not g and not p)
    fp = sum(1 for g, p in zip(gold, pred) if g and not p)
    fn = sum(1 for g, p in zip(gold, pred) if not g and p)
    tn = sum(1 for g, p in zip(gold, pred) if g and p)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    return {"accuracy": (tp + tn) / max(1, len(gold)), "defect_f1": f1, "balanced_accuracy": (rec + tnr) / 2}


def _multilabel(gold: list[list[str]], pred: list[list[str]]) -> dict:
    per = {}
    TP = FP = FN = 0
    for d in DEFECTS:
        tp = sum(1 for g, p in zip(gold, pred) if d in g and d in p)
        fp = sum(1 for g, p in zip(gold, pred) if d not in g and d in p)
        fn = sum(1 for g, p in zip(gold, pred) if d in g and d not in p)
        TP, FP, FN = TP + tp, FP + fp, FN + fn
        if tp + fn:
            per[d] = 2 * tp / (2 * tp + fp + fn)
    micro = 2 * TP / (2 * TP + FP + FN) if TP + FP + FN else 1.0
    return {"micro_f1": micro, "macro_f1": sum(per.values()) / max(1, len(per)),
            "exact_match": sum(set(g) == set(p) for g, p in zip(gold, pred)) / max(1, len(gold))}


def _statuses(gold: list[list[str]], pred: list[list[str]]) -> dict:
    pairs = [(g, p) for gs, ps in zip(gold, pred) for g, p in zip(gs, ps + [None] * (len(gs) - len(ps)))]
    f1s = []
    for c in STATUSES:
        tp = sum(1 for g, p in pairs if g == c and p == c)
        fp = sum(1 for g, p in pairs if g != c and p == c)
        fn = sum(1 for g, p in pairs if g == c and p != c)
        if tp + fn:
            f1s.append(2 * tp / (2 * tp + fp + fn))
    return {"call_accuracy": sum(g == p for g, p in pairs) / max(1, len(pairs)),
            "macro_f1": sum(f1s) / max(1, len(f1s)),
            "case_exact_match": sum(list(g) == list(p) for g, p in zip(gold, pred)) / max(1, len(gold))}


def evaluate(examples: list[dict], preds: dict[str, dict]) -> dict:
    out = {}
    for task, key, lab, fn in [
        ("T1_completeness", "complete", "label_complete", _binary),
        ("T2_fidelity", "faithful", "label_faithful", _binary),
        ("T3_defects", "defects", "label_defects", _multilabel),
        ("T4_reconstruction", "call_status", "label_call_status", _statuses),
    ]:
        have = [e for e in examples if key in preds.get(e["id"], {})]
        if not have:
            continue
        if len(have) != len(examples):
            raise ValueError(f"{task}: predictions cover {len(have)} of {len(examples)} examples")
        out[task] = fn([e[lab] for e in have], [preds[e["id"]][key] for e in have])
    return out


# ---------------------------------------------------------------- baselines

def majority(train: list[dict]):
    c = Counter(e["label_complete"] for e in train).most_common(1)[0][0]
    f = Counter(e["label_faithful"] for e in train).most_common(1)[0][0]
    s = Counter(x for e in train for x in e["label_call_status"]).most_common(1)[0][0]

    def predict(e):
        n = len(json.loads(e["emissions_json"]))
        return {"complete": c, "faithful": f, "defects": [], "call_status": [s] * n}

    return predict


def _match(em: list[dict], rec: list[dict]):
    """Match each emitted call to recorded entries: all records sharing its
    call_id when the trace carries one (a duplicated id yields several);
    failing that, the first unused record with the same name and args
    (one-to-one); else nothing."""
    by_id: dict[str, list[dict]] = {}
    for r in rec:
        if r.get("call_id"):
            by_id.setdefault(r["call_id"], []).append(r)
    used = set()
    matches = []
    for e in em:
        m = by_id.get(e["call_id"], [])
        if not m:
            # Fallback: the first unused record with the same name and arguments (one-to-one).
            m = [r for r in rec if id(r) not in used and r["name"] == e["name"] and r.get("args") == e["args"]][:1]
        for r in m:
            used.add(id(r))
        matches.append(m)
    unmatched = [r for r in rec if id(r) not in used]
    return matches, unmatched


def heuristic(e: dict) -> dict:
    """Rules a careful engineer could write without the ledger."""
    em = json.loads(e["emissions_json"])
    rec = json.loads(e["recorded_json"])
    matches, unmatched = _match(em, rec)
    interrupted = e["run_outcome"] != "completed"
    defects = set()
    status = []
    for e_, m in zip(em, matches):
        if not m:
            # Absent: the call may have run and been dropped, or never run.
            status.append("not_executed")
            defects.add("invisible_attempt" if interrupted else "missing_call")
            continue
        if len(m) > 1:
            defects.add("duplicate")
        r = m[-1]
        st = r["status"]
        status.append(st if st in ("ok", "error") else "cancelled" if interrupted else "ok")
        if st not in ("ok", "error"):
            defects.add("status_mismatch")
        if r.get("args") is not None and r["args"] != e_["args"]:
            defects.add("args_lost")
        if st == "ok" and r.get("output") is None:
            defects.add("output_lost")
        if st == "error" and not r.get("error"):
            defects.add("error_lost")
    if unmatched:
        defects.add("phantom")
    groups: dict[int, set] = {}
    for e_, m in zip(em, matches):
        for r in m:
            groups.setdefault(e_["run_index"], set()).add(r.get("group"))
    if any(len(g) > 1 for g in groups.values()):
        defects.add("isolation")
    completeness = {"missing_call", "invisible_attempt", "false_success", "status_mismatch",
                    "duplicate", "phantom", "isolation"}
    return {
        "complete": not (defects & completeness),
        "faithful": not (defects - completeness),
        "defects": [d for d in DEFECTS if d in defects],
        "call_status": status,
    }


def _fmt(results: dict[str, dict]) -> str:
    lines = []
    for name, res in results.items():
        for task, m in res.items():
            lines.append(f"| {name} | {task} | " + ", ".join(f"{k} {v:.3f}" for k, v in m.items()) + " |")
    return "| Baseline | Task | Metrics |\n|---|---|---|\n" + "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--data", default="hf-dataset/data")
    b.add_argument("--out", default="hf-dataset/tasks")
    b.add_argument("--keep-tag", action="store_true",
                   help="keep the harness tag in inputs (only for the masking ablation; write to another --out)")
    bl = sub.add_parser("baselines")
    bl.add_argument("--tasks", default="hf-dataset/tasks")
    bl.add_argument("--split", default="test")
    bl.add_argument("--out", help="write a markdown table here")
    ev = sub.add_parser("evaluate")
    ev.add_argument("predictions")
    ev.add_argument("--tasks", default="hf-dataset/tasks")
    ev.add_argument("--split", default="test")
    a = p.parse_args()
    if a.cmd == "build":
        print(json.dumps(build(Path(a.data), Path(a.out), a.keep_tag), indent=2))
    elif a.cmd == "baselines":
        td = Path(a.tasks)
        exs = load(td, a.split)
        maj = majority(load(td, "train"))
        res = {
            "majority": evaluate(exs, {e["id"]: maj(e) for e in exs}),
            "heuristic": evaluate(exs, {e["id"]: heuristic(e) for e in exs}),
        }
        table = _fmt(res)
        print(table)
        if a.out:
            Path(a.out).write_text(f"Baselines on the `{a.split}` split ({len(exs)} examples).\n\n{table}\n")
    else:
        exs = load(Path(a.tasks), a.split)
        preds = {}
        for line in Path(a.predictions).read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                preds[d["id"]] = d
        print(json.dumps(evaluate(exs, preds), indent=2))


if __name__ == "__main__":
    main()
