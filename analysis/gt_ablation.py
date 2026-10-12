"""Ground-truth ablation and dataset statistics.

Ablation: re-score every current-release case with only one of the two
ground-truth sources and compare with the full scorer.
  * emission-only: knows what the model asked for, not what ran or how it ended;
  * ledger-only: knows what ran and how it ended, not what was asked for.

Statistics: composition of the released corpus (both splits).

    python analysis/gt_ablation.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tracegap.tasks import defects_from  # noqa: E402

DATA = ROOT / "hf-dataset" / "data"
OUT = ROOT / "analysis" / "out"


def rows(split):
    return pq.read_table(DATA / f"{split}.parquet").to_pylist()


def rec_tag(r, by_id):
    a = r.get("args")
    if isinstance(a, dict) and "tag" in a:
        return a["tag"]
    return by_id.get(r.get("call_id"))


def ablate(rs):
    res = {"cases": 0, "incomplete": 0,
           "emission_only": {"detected": 0, "false_alarms": 0, "missed": Counter(), "ambiguous_missing": 0},
           "ledger_only": {"detected": 0, "false_alarms": 0, "missed": Counter()},
           "ledger_only_lenient": {"detected": 0, "false_alarms": 0, "missed": Counter()}}
    for r in rs:
        if not r["calibrated"] or r["harness_error"]:
            continue
        em = json.loads(r["emissions_json"])
        led = json.loads(r["ledger_json"])
        rec = json.loads(r["recorded_json"])
        by_id = {e["call_id"]: e["tag"] for e in em}
        ran = {x["tag"] for x in led}
        emitted = [e["tag"] for e in em]
        rec_tags = [rec_tag(x, by_id) for x in rec]
        full = set(defects_from(r["failures"], []))
        incomplete = not r["complete"]
        res["cases"] += 1
        res["incomplete"] += incomplete
        # emission-only: every emitted call must appear; no record may be unmatched or repeated
        cnt = Counter(t for t in rec_tags if t is not None)
        e_flag = (any(t not in cnt for t in emitted) or any(t is None or t not in emitted for t in rec_tags)
                  or any(cnt[t] > 1 for t in emitted))
        eo = res["emission_only"]
        if incomplete and e_flag:
            eo["detected"] += 1
        if not incomplete and e_flag:
            eo["false_alarms"] += 1
        if incomplete and not e_flag:
            eo["missed"].update(full)
        if full & {"missing_call", "invisible_attempt"}:
            eo["ambiguous_missing"] += 1  # cannot tell "ran but dropped" from "never ran"
        # ledger-only: every executed call must appear with an honest status; records of calls
        # that never ran look like phantoms
        lo = res["ledger_only"]
        status = {x["tag"]: x["status"] for x in led}
        l_flag = False
        for t in ran:
            hits = [x for x, tt in zip(rec, rec_tags) if tt == t]
            if not hits:
                l_flag = True
            elif len(hits) > 1:
                l_flag = True
            else:
                st = hits[0]["status"]
                if st == "ok" and status[t] != "ok":
                    l_flag = True
                if status[t] == "ok" and st in ("error", "incomplete"):
                    l_flag = True
        l_core = l_flag
        if any(t is None or t not in ran for t in rec_tags):
            l_flag = True  # a record without an executed call: phantom from the ledger's view
        # lenient: tolerate records of calls the ledger never saw unless they claim success
        l_len = l_core or any((t is None or t not in ran) and x["status"] == "ok" for x, t in zip(rec, rec_tags))
        ll = res["ledger_only_lenient"]
        if incomplete and l_len:
            ll["detected"] += 1
        if not incomplete and l_len:
            ll["false_alarms"] += 1
        if incomplete and not l_len:
            ll["missed"].update(full)
        if incomplete and l_flag:
            lo["detected"] += 1
        if not incomplete and l_flag:
            lo["false_alarms"] += 1
        if incomplete and not l_flag:
            lo["missed"].update(full)
    for k in ("emission_only", "ledger_only", "ledger_only_lenient"):
        res[k]["missed"] = dict(res[k]["missed"])
    return res


def stats(allrows):
    s = Counter()
    labels = Counter()
    status = Counter()
    for r in allrows:
        s["cases"] += 1
        s["calibrated"] += bool(r["calibrated"])
        em = json.loads(r["emissions_json"])
        led = json.loads(r["ledger_json"])
        rec = json.loads(r["recorded_json"])
        s["emitted"] += len(em)
        s["executed"] += len(led)
        s["never_executed"] += len({e["tag"] for e in em} - {x["tag"] for x in led})
        s["records"] += len(rec)
        for x in led:
            status[x["status"]] += 1
        s["incomplete"] += not r["complete"]
        s["unfaithful"] += not r["faithful"]
        s["stress"] += r["tier"] == "stress"
        if r["calibrated"] and not r["harness_error"]:
            for d in defects_from(r["failures"], r["fidelity_failures"]):
                labels[d] += 1
        s["false_success_calls"] += r["misreported_ok"] or 0
        s["duplicates"] += r["duplicates"] or 0
        s["phantoms"] += r["phantoms"] or 0
    return {"counts": dict(s), "ledger_status": dict(status), "defect_labels": dict(labels)}


def main():
    cur = rows("current")
    hist = rows("history")
    out = {"ablation_current": ablate(cur), "ablation_all": ablate(cur + hist),
           "stats_current": stats(cur), "stats_history": stats(hist), "stats_all": stats(cur + hist)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gt_ablation.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
