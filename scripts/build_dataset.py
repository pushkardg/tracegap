#!/usr/bin/env python3
"""Package TraceGap results as a Hugging Face dataset (Parquet + dataset card).

Inputs (all optional except the first):
  results/results.json              current versions, fixed suite
  results/traces/*.jsonl            its trace corpus
  results/generated/...             current versions, generated suite
  results/versions/<fw>/<ver>.json  version matrix, fixed suite (+ traces)

Output: hf-dataset/ with data/*.parquet and README.md (dataset card).

    python scripts/build_dataset.py --out hf-dataset
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COUNTERS = [
    "executed", "executed_recorded", "status_checked", "status_correct", "misreported_ok", "args_checked",
    "args_exact", "output_checked", "output_exact", "output_truncated", "unexecuted", "unexecuted_visible",
    "phantoms", "duplicates", "unattributed", "isolation_violations", "fragmented_runs", "orphaned_tools",
]


def _traces(trace_dir: Path) -> dict:
    idx = {}
    if not trace_dir.exists():
        return idx
    for f in trace_dir.rglob("*.jsonl"):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            idx[(r["adapter"], r["scenario"], r["mode"])] = r
    return idx


def rows_from(results_file: Path, trace_dir: Path, suite: str, split: str, unstable=None) -> list[dict]:
    """unstable: None = stability not checked; otherwise the set of (adapter, scenario, mode)
    keys whose verdict differed between repeated runs."""
    data = json.loads(results_file.read_text())
    tr = _traces(trace_dir)
    from tracegap.tiers import tiers_for  # noqa: PLC0415

    tmap = tiers_for(data)
    rows = []
    # S01 (one successful call) calibrates each surface; see scripts/history_report.py.
    calib = {}
    for r in data["results"]:
        if r["scenario"] == "S01":
            calib[r["adapter"]] = calib.get(r["adapter"], True) and r["passed"]
    for r in data["results"]:
        fw, surface = r["adapter"].split("/", 1)
        meta = data["scenarios"][r["scenario"]]
        key = (r["adapter"], r["scenario"], r["mode"])
        if key not in tr:
            raise SystemExit(f"missing trace for {key} under {trace_dir}. Traces for the generated suite and the "
                             "version history are not in git; re-run scripts/run_all.sh / run_versions.py first, "
                             "or use the released Parquet files in hf-dataset/data as the canonical corpus.")
        t = tr[key]
        row = {
            "split": split,
            "suite": suite,
            "benchmark_version": data["version"],
            "framework": fw,
            "surface": surface,
            "framework_version": data["adapters"][r["adapter"]]["version"],
            "scenario_id": r["scenario"],
            "category": meta["category"],
            "scenario_title": meta["title"],
            "scenario_description": meta["description"],
            "mode": r["mode"],
            "tier": tmap[r["scenario"]],
            "calibrated": calib.get(r["adapter"], True) and r["run_outcome"] != "harness-error",
            "stable": None if unstable is None else (r["adapter"], r["scenario"], r["mode"]) not in unstable,
            "complete": r["complete"],
            "faithful": r["faithful"],
            "run_outcome": r["run_outcome"],
            "harness_error": r.get("error"),
            "failures": r["failures"],
            "fidelity_failures": r["fidelity_failures"],
            "emissions_json": json.dumps(t.get("emissions", []), ensure_ascii=False, default=str),
            "ledger_json": json.dumps(t.get("ledger", []), ensure_ascii=False, default=str),
            "recorded_json": json.dumps(t.get("recorded", []), ensure_ascii=False, default=str),
        }
        for c in COUNTERS:
            row[c] = r.get(c, 0)
        rows.append(row)
    return rows


def write(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "hf-dataset"))
    p.add_argument("--repo", default="https://github.com/pushkardg/tracegap")
    a = p.parse_args()
    out = Path(a.out)
    res = ROOT / "results"
    stats = {}

    # Core suite: identical verdicts in three full runs.
    current = rows_from(res / "results.json", res / "traces", "core", "current", unstable=set())
    gen_root = res / "generated"
    gen_desc = "not included"
    if (gen_root / "results.json").exists():
        data = json.loads((gen_root / "results.json").read_text())
        gen_desc = data.get("suite", "generated")
        uf = gen_root / "unstable_cases.json"
        unstable = {tuple(k) for k in json.loads(uf.read_text())} if uf.exists() else None
        current += rows_from(gen_root / "results.json", gen_root / "traces", gen_desc, "current", unstable=unstable)
    write(current, out / "data" / "current.parquet")
    stats["current"] = len(current)

    history = []
    vroot = res / "versions"
    if vroot.exists():
        for f in sorted(vroot.glob("*/*.json")):
            fw, ver = f.parent.name, f.stem
            results = json.loads(f.read_text())["results"]
            if not results or all(r["run_outcome"] == "harness-error" for r in results):
                continue  # version not covered (listed in HISTORY.md); no trace information
            history += rows_from(f, vroot / "traces" / fw / ver, "core", "history")
    write(history, out / "data" / "history.parquet")
    stats["history"] = len(history)
    from tracegap import tasks  # noqa: PLC0415

    tstats = tasks.build(out / "data", out / "tasks")
    stats["tasks"] = {k: v["examples"] for k, v in tstats.items()}
    test = tasks.load(out / "tasks", "test")
    maj = tasks.majority(tasks.load(out / "tasks", "train"))
    base = {
        "majority": tasks.evaluate(test, {e["id"]: maj(e) for e in test}),
        "heuristic": tasks.evaluate(test, {e["id"]: tasks.heuristic(e) for e in test}),
    }
    (out / "tasks" / "BASELINES.md").write_text(
        f"Baselines on the `test` split ({len(test)} examples).\n\n{tasks._fmt(base)}\n")
    (out / "stats.json").write_text(json.dumps(stats, indent=2))
    write_card(out, current, history, gen_desc, a.repo, tstats, base)
    print(json.dumps(stats))



CARD = """---
license: cc-by-4.0
pretty_name: TraceGap
language:
- en
tags:
- llm-agents
- observability
- tracing
- opentelemetry
- provenance
- benchmark
size_categories:
- {size_cat}
task_categories:
- other
configs:
- config_name: default
  data_files:
  - split: current
    path: data/current.parquet
  - split: history
    path: data/history.parquet
- config_name: tasks
  data_files:
  - split: train
    path: tasks/train.parquet
  - split: validation
    path: tasks/validation.parquet
  - split: test
    path: tasks/test.parquet
---

# TraceGap: Measuring Whether LLM Agent Frameworks Record the Tool Calls Their Agents Make

*The agent tracing correctness benchmark: does your agent framework record what actually happened?*

This is the dataset release of TraceGap. It has two configurations:

- `default`: the full labeled corpus, one row per test case, with all three logs and the scorer's verdicts (splits `current` and `history`).
- `tasks`: the same cases packaged as four learning tasks (T1–T4, plus the adapter task T5 scored by the benchmark) with the ground-truth ledger hidden, split by framework (splits `train`, `validation`, `test`).

```python
from datasets import load_dataset
corpus = load_dataset("pushkardg/tracegap")             # current, history
tasks = load_dataset("pushkardg/tracegap", "tasks")     # train, validation, test
```

Each row is one test case: an agent framework driven by a scripted model through a scenario, with three aligned logs.

- `emissions_json`: the tool calls the model asked for.
- `ledger_json`: the tool calls that actually ran, with real arguments and real outcomes, written by the tools themselves.
- `recorded_json`: what the framework's trace surface reported (callbacks, tracing spans, OpenTelemetry or OpenInference spans, message history, or events).

Each case is labeled `complete` (every call present with an honest status) and `faithful` (arguments, outputs and errors exact). The `failures` and `fidelity_failures` columns say why when a label is false.

The data comes from the TraceGap benchmark (code, scenarios and method: {repo}). No API keys or network were used; models are scripted, so every row is reproducible.

## Splits

| Split | Rows | What it is |
|---|---|---|
| `current` | {n_current} | Latest release of each framework: the 22 hand-written scenarios, plus a seeded generated suite ({gen_desc}) |
| `history` | {n_history} | The 22 hand-written scenarios across {n_versions} released versions; dependencies resolved as of each release date where possible |

Frameworks: {frameworks}.

## Columns

`framework`, `surface`, `framework_version`, `suite`, `scenario_id`, `category`, `scenario_title`, `scenario_description`, `mode` (invoke or stream), `tier` (stable or stress), `calibrated`, `stable`, `complete`, `faithful`, `run_outcome`, `harness_error`, `failures`, `fidelity_failures`, the three JSON logs, and per-case counters (`executed`, `executed_recorded`, `status_correct`, `misreported_ok`, `unexecuted`, `unexecuted_visible`, `phantoms`, `duplicates`, `isolation_violations`, `fragmented_runs`, `orphaned_tools`, and others).

`tier` is the scenario's tier: **stress** when a tool raises inside a parallel batch (verdicts there can depend on scheduling), **stable** otherwise. Use stable rows for comparisons between frameworks. `stable` is false for the 148 generated cases whose verdict differed between any of three full runs; all of them are in the stress tier, where the framework's handling of the sibling calls is a race (see `results/generated/STABILITY.md`). `stable` is null in the history split, where stability was not checked.

`calibrated` is false when the surface fails the calibration case S01 (one successful call) for that framework version. Such rows mean the surface is absent in that version, or reports in a format the adapter does not read. Exclude them when comparing versions.

## Example row (`default`, abridged)

```json
{example}
```

## Tasks (`tasks` configuration)

A real observability pipeline sees the calls a model emitted and the trace a framework recorded, but not what really ran. The tasks hide the ledger and ask a method to recover facts about it. Inputs per example: `framework`, `surface`, `framework_version`, `mode`, `suite`, `tier`, `run_outcome`, `emissions_json` and `recorded_json`. The harness's unique `tag` argument is removed from both, since production tools have none; join calls by call id.

| Task | Predict | Label column | Metrics |
|---|---|---|---|
| T1 Completeness detection | Is the recorded trace complete? | `label_complete` | defect F1, balanced accuracy |
| T2 Fidelity detection | Are recorded arguments, outputs and errors exact? | `label_faithful` | defect F1, balanced accuracy |
| T3 Defect classification | Which defect types are present (multi-label)? | `label_defects` | micro and macro F1 |
| T4 Execution reconstruction | For each emitted call: `ok`, `error`, `cancelled`, `running` or `not_executed` | `label_call_status` | per-call accuracy, macro F1, case exact match |
| T5 Trace normalization | Convert a framework's native trace into the canonical record | (scored by the benchmark) | Complete and Faithful rates on the TraceGap suites |

Defect labels for T3: `missing_call`, `invisible_attempt`, `false_success`, `status_mismatch`, `duplicate`, `phantom`, `isolation`, `args_lost`, `output_lost`, `error_lost`. They are derived mechanically from the scorer's failure reasons (`tracegap/tasks.py`). Labels that do not occur in a split are skipped by macro F1.

Splits hold out whole frameworks, so a method must generalize to an unseen framework's trace conventions:

| Split | Frameworks | Examples |
|---|---|---|
| `train` | {train_fw} | {n_train} |
| `validation` | {val_fw} | {n_val} |
| `test` | {test_fw} | {n_test} |

Uncalibrated rows and rows with a harness error are excluded. T5 has no rows here: native traces are produced live by running the framework, so T5 is scored by writing an adapter and running `python -m tracegap.check_adapter` and the benchmark.

Evaluate predictions (JSON lines with `id` and any of `complete`, `faithful`, `defects`, `call_status`):

```bash
pip install "tracegap[tasks]"
python -m tracegap.tasks evaluate predictions.jsonl --tasks path/to/tasks --split test
```

### Baselines (test split)

{baselines}

The heuristic matches emitted calls to recorded ones by call id and, failing that, one-to-one by name and arguments, and applies rules a careful engineer could write without the ledger. It detects missing calls well but cannot tell a dropped call from one that never ran, and it misses most fidelity losses, so there is clear room for learned methods.

## Uses

- **Testing trace validators, observability back ends and provenance tools.** Feed `recorded_json` in and compare what they report against `ledger_json`.
- **Studying how trace completeness changes across releases** (`history` split).
- **Regression tests** for agent frameworks' observability layers.

Not suitable for evaluating model quality: the models are scripted.

## Citation

```bibtex
{bibtex}
```

Cite the Zenodo concept DOI for the benchmark in general, or a version DOI for exact reproducibility (see `CITATION.cff` in the repository).
"""


def size_category(n: int) -> str:
    for lim, lab in [(1_000, "n<1K"), (10_000, "1K<n<10K"), (100_000, "10K<n<100K")]:
        if n < lim:
            return lab
    return "100K<n<1M"


BIBTEX = """@misc{{gopalakrishna2026tracegap,
  title  = {{TraceGap: Measuring Whether {{LLM}} Agent Frameworks Record the Tool Calls Their Agents Make}},
  author = {{Gopalakrishna, Pushkar Devanahalli}},
  year   = {{2026}},
  note   = {{Benchmark and dataset, version {version}}},
  doi    = {{10.5281/zenodo.23324532}},
  url    = {{{repo}}}
}}"""


def _example(current: list[dict]) -> str:
    r = next(x for x in current if x["scenario_id"] == "S17" and not x["complete"])
    keep = ["framework", "surface", "framework_version", "scenario_id", "scenario_title", "mode", "tier",
            "complete", "faithful", "run_outcome", "failures", "emissions_json", "ledger_json", "recorded_json"]
    d = {k: r[k] for k in keep}
    for k in ("emissions_json", "ledger_json", "recorded_json"):
        d[k] = json.loads(d[k])
    return json.dumps(d, indent=2)


def write_card(out: Path, current: list[dict], history: list[dict], gen_desc: str, repo: str,
               tstats: dict, base: dict) -> None:
    from tracegap import tasks  # noqa: PLC0415

    fws = sorted({r["framework"] for r in current})
    versions = {(r["framework"], r["framework_version"]) for r in history}
    citation = (ROOT / "CITATION.cff").read_text() if (ROOT / "CITATION.cff").exists() else ""
    card = CARD.format(
        size_cat=size_category(len(current) + len(history)), repo=repo, n_current=len(current),
        n_history=len(history), gen_desc=gen_desc, n_versions=len(versions), frameworks=", ".join(fws),
        citation=citation.strip(),
        bibtex=BIBTEX.format(version=current[0]["benchmark_version"], repo=repo),
        example=_example(current),
        baselines=tasks._fmt(base),
        train_fw=", ".join(tstats["train"]["frameworks"]), n_train=tstats["train"]["examples"],
        val_fw=", ".join(tstats["validation"]["frameworks"]), n_val=tstats["validation"]["examples"],
        test_fw=", ".join(tstats["test"]["frameworks"]), n_test=tstats["test"]["examples"],
    )
    (out / "README.md").write_text(card)


if __name__ == "__main__":
    main()
