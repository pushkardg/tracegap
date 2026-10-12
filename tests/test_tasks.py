import json

from tracegap.tasks import DEFECTS, call_status, defects_from, evaluate, heuristic, strip_emissions


def test_defect_mapping():
    got = defects_from(
        ["t1: executed (ok) but missing from trace", "t2: actual=cancelled but trace status=ok",
         "t3: emitted but never executed, and the attempt is invisible in the trace",
         "t4: actual=ok but trace status=incomplete", "t5: recorded 2 times but executed 1 time(s)",
         "phantom: trace has call 'x' the model never emitted", "run 0: its calls are split across 2 unrelated trace groups"],
        ["t1: args differ: trace=None actual={}", "t1: output missing: trace=None actual='a'",
         "t2: error message not recorded (actual='boom')"],
    )
    assert got == DEFECTS


def test_call_status_and_strip():
    em = [{"call_id": "c1", "name": "echo", "args": {"tag": "a"}, "tag": "a", "run_index": 0},
          {"call_id": "c2", "name": "echo", "args": {"tag": "b"}, "tag": "b", "run_index": 0}]
    led = [{"tag": "a", "status": "cancelled"}]
    assert call_status(em, led) == ["cancelled", "not_executed"]
    assert all("tag" not in e for e in strip_emissions(em))


def test_heuristic_and_evaluate_perfect_trace():
    em = [{"call_id": "c1", "name": "echo", "args": {"tag": "a"}, "run_index": 0}]
    rec = [{"name": "echo", "args": {"tag": "a"}, "status": "ok", "output": "echo:a", "error": None,
            "call_id": "c1", "group": "g", "order": 1}]
    ex = {"id": "x", "emissions_json": json.dumps(em), "recorded_json": json.dumps(rec), "run_outcome": "completed",
          "label_complete": True, "label_faithful": True, "label_defects": [], "label_call_status": ["ok"]}
    p = heuristic(ex)
    assert p == {"complete": True, "faithful": True, "defects": [], "call_status": ["ok"]}
    m = evaluate([ex], {"x": p})
    assert m["T4_reconstruction"]["call_accuracy"] == 1.0
    assert m["T3_defects"]["exact_match"] == 1.0


def test_tag_is_masked_from_task_inputs():
    from tracegap.tasks import strip_recorded

    em = [{"call_id": "c1", "name": "record", "args": {"tag": "t1"}, "tag": "t1", "run_index": 0}]
    rec = [{"name": "record", "args": {"tag": "t1"}, "status": "ok", "output": {"tag": "t1", "items": [1]},
            "error": None, "call_id": "c1"},
           {"name": "big", "args": {"tag": "t1", "size": 3}, "status": "error", "output": None,
            "error": "t1:xxx failed for n2", "call_id": "c2"}]
    e2 = strip_emissions(em)
    r2 = strip_recorded(rec, {"t1", "n2"})  # emission and ledger tags of the case
    assert e2[0]["args"] == {} and "tag" not in e2[0]
    assert r2[0]["args"] == {} and r2[0]["output"] == {"items": [1]}
    assert r2[1]["args"] == {"size": 3} and "t1" not in r2[1]["error"] and "n2" not in r2[1]["error"]
    assert strip_recorded(rec, {"t1"}, keep_tag=True) == rec


def test_match_fallback_is_one_to_one():
    from tracegap.tasks import _match

    em = [{"call_id": "x1", "name": "nothing", "args": {}}, {"call_id": "x2", "name": "nothing", "args": {}}]
    rec = [{"name": "nothing", "args": {}, "call_id": None}, {"name": "nothing", "args": {}, "call_id": None}]
    matches, unmatched = _match(em, rec)
    assert [len(m) for m in matches] == [1, 1] and not unmatched
