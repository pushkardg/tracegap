---
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
- 10K<n<100K
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

The data comes from the TraceGap benchmark (code, scenarios and method: https://github.com/pushkardg/tracegap). No API keys or network were used; models are scripted, so every row is reproducible.

## Splits

| Split | Rows | What it is |
|---|---|---|
| `current` | 6660 | Latest release of each framework: the 22 hand-written scenarios, plus a seeded generated suite (generated(n=200, seed=1)) |
| `history` | 4884 | The 22 hand-written scenarios across 65 released versions; dependencies resolved as of each release date where possible |

Frameworks: autogen, crewai, google-adk, langgraph, llamaindex, openai-agents, pydantic-ai, semantic-kernel, smolagents.

## Columns

`framework`, `surface`, `framework_version`, `suite`, `scenario_id`, `category`, `scenario_title`, `scenario_description`, `mode` (invoke or stream), `tier` (stable or stress), `calibrated`, `stable`, `complete`, `faithful`, `run_outcome`, `harness_error`, `failures`, `fidelity_failures`, the three JSON logs, and per-case counters (`executed`, `executed_recorded`, `status_correct`, `misreported_ok`, `unexecuted`, `unexecuted_visible`, `phantoms`, `duplicates`, `isolation_violations`, `fragmented_runs`, `orphaned_tools`, and others).

`tier` is the scenario's tier: **stress** when a tool raises inside a parallel batch (verdicts there can depend on scheduling), **stable** otherwise. Use stable rows for comparisons between frameworks. `stable` is false for the 148 generated cases whose verdict differed between any of three full runs; all of them are in the stress tier, where the framework's handling of the sibling calls is a race (see `results/generated/STABILITY.md`). `stable` is null in the history split, where stability was not checked.

`calibrated` is false when the surface fails the calibration case S01 (one successful call) for that framework version. Such rows mean the surface is absent in that version, or reports in a format the adapter does not read. Exclude them when comparing versions.

## Example row (`default`, abridged)

```json
{
  "framework": "autogen",
  "surface": "messages",
  "framework_version": "autogen-agentchat 0.7.5, autogen-core 0.7.5",
  "scenario_id": "S17",
  "scenario_title": "Cancelled during a tool",
  "mode": "invoke",
  "tier": "stable",
  "complete": false,
  "faithful": true,
  "run_outcome": "cancelled",
  "failures": [
    "t1: executed (ok) but missing from trace",
    "t2: executed (running) but missing from trace"
  ],
  "emissions_json": [
    {
      "run_index": 0,
      "call_id": "call_r0_t1",
      "name": "echo",
      "args": {
        "tag": "t1",
        "text": "before"
      },
      "tag": "t1",
      "nested": false
    },
    {
      "run_index": 0,
      "call_id": "call_r0_t2",
      "name": "slow",
      "args": {
        "tag": "t2",
        "seconds": 2.0
      },
      "tag": "t2",
      "nested": false
    }
  ],
  "ledger_json": [
    {
      "tag": "t1",
      "name": "echo",
      "args": {
        "tag": "t1",
        "text": "before"
      },
      "status": "ok",
      "output": "echo:before",
      "error": null,
      "seq_start": 1,
      "seq_end": 2
    },
    {
      "tag": "t2",
      "name": "slow",
      "args": {
        "tag": "t2",
        "seconds": 2.0
      },
      "status": "running",
      "output": null,
      "error": null,
      "seq_start": 3,
      "seq_end": null
    }
  ],
  "recorded_json": []
}
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
| `train` | autogen, crewai, langgraph, llamaindex, pydantic-ai | 5884 |
| `validation` | openai-agents, semantic-kernel | 2344 |
| `test` | google-adk, smolagents | 2832 |

Uncalibrated rows and rows with a harness error are excluded. T5 has no rows here: native traces are produced live by running the framework, so T5 is scored by writing an adapter and running `python -m tracegap.check_adapter` and the benchmark.

Evaluate predictions (JSON lines with `id` and any of `complete`, `faithful`, `defects`, `call_status`):

```bash
pip install "tracegap[tasks]"
python -m tracegap.tasks evaluate predictions.jsonl --tasks path/to/tasks --split test
```

### Baselines (test split)

| Baseline | Task | Metrics |
|---|---|---|
| majority | T1_completeness | accuracy 0.626, defect_f1 0.000, balanced_accuracy 0.500 |
| majority | T2_fidelity | accuracy 0.875, defect_f1 0.000, balanced_accuracy 0.500 |
| majority | T3_defects | micro_f1 0.000, macro_f1 0.000, exact_match 0.589 |
| majority | T4_reconstruction | call_accuracy 0.764, macro_f1 0.173, case_exact_match 0.383 |
| heuristic | T1_completeness | accuracy 0.817, defect_f1 0.795, balanced_accuracy 0.843 |
| heuristic | T2_fidelity | accuracy 0.819, defect_f1 0.085, balanced_accuracy 0.497 |
| heuristic | T3_defects | micro_f1 0.373, macro_f1 0.258, exact_match 0.466 |
| heuristic | T4_reconstruction | call_accuracy 0.741, macro_f1 0.404, case_exact_match 0.601 |

The heuristic matches emitted calls to recorded ones by call id and, failing that, one-to-one by name and arguments, and applies rules a careful engineer could write without the ledger. It detects missing calls well but cannot tell a dropped call from one that never ran, and it misses most fidelity losses, so there is clear room for learned methods.

## Uses

- **Testing trace validators, observability back ends and provenance tools.** Feed `recorded_json` in and compare what they report against `ledger_json`.
- **Studying how trace completeness changes across releases** (`history` split).
- **Regression tests** for agent frameworks' observability layers.

Not suitable for evaluating model quality: the models are scripted.

## Citation

```bibtex
@misc{gopalakrishna2026tracegap,
  title  = {TraceGap: Measuring Whether {LLM} Agent Frameworks Record the Tool Calls Their Agents Make},
  author = {Gopalakrishna, Pushkar Devanahalli},
  year   = {2026},
  note   = {Benchmark and dataset, version 1.0.0},
  url    = {https://github.com/pushkardg/tracegap}
}
```

Cite the Zenodo concept DOI for the benchmark in general, or a version DOI for exact reproducibility (see `CITATION.cff` in the repository).
