# TraceGap

**The agent tracing correctness benchmark.**

### Does your agent framework record what actually happened?

[![PyPI](https://img.shields.io/pypi/v/tracegap)](https://pypi.org/project/tracegap/)
[![CI](https://github.com/pushkardg/tracegap/actions/workflows/ci.yml/badge.svg)](https://github.com/pushkardg/tracegap/actions/workflows/ci.yml)
[![Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20dataset-tracegap-yellow)](https://huggingface.co/datasets/pushkardg/tracegap)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23324532.svg)](https://doi.org/10.5281/zenodo.23324532)
[![License](https://img.shields.io/badge/license-MIT%20%2B%20CC%20BY%204.0-blue)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)
[![Frameworks](https://img.shields.io/badge/frameworks-9-purple)](#leaderboard)

TraceGap tests LLM agent frameworks for missing, duplicated, misclassified and corrupted tool-call records across failures, cancellation, parallel execution, rejected calls and nested agents.

Agent benchmarks usually score the *model*. TraceGap scores the *framework's record*: its callbacks, tracing spans, OpenTelemetry or OpenInference output, events or message history. That record is what dashboards, audit logs, incident reviews and evaluation pipelines are built on. If a tool call is missing, or a cancelled call is shown as a success, everything downstream inherits the error.

No API keys and no network: every framework is driven by a scripted model, so a run takes minutes and the same inputs give the same verdicts.

**[Quick start](#quick-start) · [Leaderboard](#leaderboard) · [Add your framework](#add-your-framework) · [Dataset](#dataset) · [Paper](#paper)**

## Quick start

```bash
pip install tracegap              # add [tasks] for the dataset tasks: pip install "tracegap[tasks]"
pip install langgraph            # the framework(s) you want to test
tracegap -v                      # run every adapter whose framework is installed; writes tracegap-results/
```

Each line of output is one case: `[CF]` complete and faithful, `[C-]` complete but detail lost, `[-F]` incomplete but what was recorded is exact, `[--]` incomplete and inexact, with the reason under `-v`. Useful options:

```bash
tracegap --adapters langgraph --scenarios S17 S18      # a subset
tracegap --tier stable --fail-on incomplete            # CI: deterministic cases, fail on any gap
tracegap --suite generated --n 200 --seed 1            # the seeded generated suite
tracegap --baseline old.json                           # fail only on regressions
python -m tracegap.report results/results.json --out CORE.md --leaderboard LEADERBOARD.md
```

### In CI

GitHub Action, which writes the results to the job summary and uploads them as an artifact:

```yaml
- uses: pushkardg/tracegap@v1
  with:
    install: "-e ."                                    # the framework under test
    adapter-module: "mypkg.tracegap_adapter:MyAdapter" # or adapters: langgraph
    tier: stable                                       # deterministic cases only (default)
    baseline: tracegap-baseline.json                   # fail only on regressions
```

Or pytest, where each scenario is a test and known gaps are strict xfails (the suite tells you when you fix one, and fails if you regress one):

```python
import pytest
from tracegap.testing import cases, check
from mypkg.tracegap_adapter import MyAdapter

@pytest.mark.parametrize("case", cases(MyAdapter, known_gaps={"S08"}))
def test_tracegap(case):
    check(case)
```

## Leaderboard

### TraceGap agent trace reliability leaderboard (v1.0)

Ranked on the **Stable** tier: every scenario whose verdicts are deterministic, from the 22 hand-written core scenarios and the 200 generated ones, each in invoke and stream mode. Capability columns count complete Stable cases among the core scenarios for tool failures (S05–S06), cancellation (S17–S18), rejected calls (S08–S10) and nested agents (S22). **Stress** cases, where a tool raises inside a parallel batch and some frameworks race, are scored separately and not ranked.

<!-- LEADERBOARD:START -->
| # | Framework / surface | Version | Complete | Faithful | Tool failures | Cancellation | Rejected calls | Nested agents | Stress: complete |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `crewai/events` | crewai 1.15.23 | **100.0%** | 100.0% | ✅ 4/4 | ✅ 4/4 | ✅ 6/6 | ✅ 2/2 | 100.0% |
| 2 | `google-adk/otel` | google-adk 2.11.0 | **92.2%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ✅ 6/6 | ✅ 2/2 | 99.2% |
| 3 | `llamaindex/events` | llama-index-core 0.14.25 | **91.3%** | 100.0% | ✅ 4/4 | ✅ 4/4 | ✅ 6/6 | ✅ 2/2 | 82.4% |
| 4 | `pydantic-ai/history` | pydantic-ai-slim 2.54.0 | **89.8%** | 90.3% | ✅ 4/4 | ✅ 4/4 | ✅ 6/6 | ❌ 0/2 | 48.3% |
| 5 | `pydantic-ai/otel` | pydantic-ai-slim 2.54.0 | **80.6%** | 100.0% | ✅ 4/4 | ✅ 4/4 | ⚠️ 4/6 | ✅ 2/2 | 77.3% |
| 6 | `autogen/otel` | autogen-agentchat 0.7.5 | **77.7%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ⚠️ 4/6 | ✅ 2/2 | 62.2% |
| 7 | `langgraph/callbacks` | langgraph 1.2.12 | **77.7%** | 100.0% | ✅ 4/4 | ✅ 4/4 | ⚠️ 4/6 | ✅ 2/2 | 59.7% |
| 8 | `google-adk/events` | google-adk 2.11.0 | **77.7%** | 66.0% | ✅ 4/4 | ✅ 4/4 | ✅ 6/6 | ✅ 2/2 | 14.3% |
| 9 | `openai-agents/tracing` | openai-agents 0.23.1 | **76.7%** | 90.3% | ✅ 4/4 | ⚠️ 2/4 | ⚠️ 4/6 | ✅ 2/2 | 62.2% |
| 10 | `autogen/messages` | autogen-agentchat 0.7.5 | **74.3%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ✅ 6/6 | ❌ 0/2 | 74.4% |
| 11 | `llamaindex/openinference` | llama-index-core 0.14.25 | **69.9%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ⚠️ 4/6 | ✅ 2/2 | 47.9% |
| 12 | `semantic-kernel/filters` | semantic-kernel 1.44.1 | **67.0%** | 100.0% | ✅ 4/4 | ✅ 4/4 | ⚠️ 2/6 | ✅ 2/2 | 48.7% |
| 13 | `semantic-kernel/otel` | semantic-kernel 1.44.1 | **60.2%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ⚠️ 2/6 | ✅ 2/2 | 40.3% |
| 14 | `smolagents/openinference` | smolagents 1.26.0 | **44.7%** | 100.0% | ✅ 4/4 | ⚠️ 2/4 | ❌ 0/6 | ✅ 2/2 | 29.4% |
| 15 | `smolagents/memory` | smolagents 1.26.0 | **38.8%** | 100.0% | ❌ 0/4 | ⚠️ 2/4 | ❌ 0/6 | ✅ 2/2 | 5.9% |

Stable tier: 2,304 of 3,090 cases complete (74.6%). Stress tier: 2,028 of 3,570 (56.8%).
<!-- LEADERBOARD:END -->

Complete: every executed call present with an honest status, no phantoms or duplicates, runs neither mixed nor split. Faithful: every captured argument, output and error message exact. Full tables: [`results/LEADERBOARD.md`](results/LEADERBOARD.md); per-suite scenario matrices and every failure reason: [`results/CORE.md`](results/CORE.md) and [`results/generated/LEADERBOARD.md`](results/generated/LEADERBOARD.md); an HTML version: [`site/index.html`](site/index.html).

Framework versions are pinned in [`envs/`](envs/); results apply to those versions. History across 65 past releases: [`results/HISTORY.md`](results/HISTORY.md).

### What the failures have in common

1. **Cancelled calls are reported as successful.** OpenTelemetry's `use_span` records only `Exception`, and `asyncio.CancelledError` is a `BaseException`. A framework that wraps tool execution in `except Exception` closes a cancelled tool's span with an unset status, which back ends show as success. Affected: OpenAI Agents SDK, Semantic Kernel, Google ADK, and AutoGen once its orphaned-tool bug is fixed. TraceGap does not require cancellation to be recorded as an *error*, only that a call which never finished does not read as a success.
2. **Failed runs lose calls that had already succeeded.** AutoGen's `TaskResult.messages` exists only if the run completes. When one call in a parallel batch raises, Google ADK's events and Pydantic AI's history drop the results of siblings that succeeded. smolagents' memory drops every call of a step in which any call failed.
3. **Rejected calls leave no tool-level trace.** A call to an unknown tool, or with invalid arguments, is often visible only in raw model output.
4. **Nested agents vanish from per-agent histories,** though they appear in tracing and OpenTelemetry surfaces.
5. **Error details are withheld.** The OpenAI Agents SDK redacts tool errors from spans under its default error handler since 0.23. Several history and event surfaces have no record of the error when a tool raises.
6. **Cancellation does not always stop work.** AutoGen, LlamaIndex (when `stream_events()` is cancelled), smolagents and CrewAI let an in-flight tool finish after the caller has seen the run cancelled.

Some of these are deliberate design choices; redaction, for example, protects sensitive data. TraceGap reports them because anyone relying on the trace needs to know.

### Defects found, with fixes

| Project | Defect | Fix |
|---|---|---|
| OpenAI Agents SDK | cancelled function span has no error | [`openai-agents-cancelled-tool-span.patch`](upstream-fixes/) |
| AutoGen | `run()` hangs after `CancellationToken` cancel during a tool; in-flight tool keeps running after task cancel; cancelled tool span unset | [`autogen-assistant-agent-tool-cancellation.patch`](upstream-fixes/) |
| Semantic Kernel | cancelled function span unset | [`semantic-kernel-cancelled-function-span.patch`](upstream-fixes/) |
| Google ADK | cancelled tool span unset (including cancelled parallel siblings) | [`google-adk-cancelled-tool-span.patch`](upstream-fixes/) |
| smolagents | step memory loses all tool calls when one fails; duplicate call ids silently dropped (issue only) | [`smolagents-memory-failed-step-tool-calls.patch`](upstream-fixes/) |

Each fix has a regression test that fails before and passes after. Standalone reproductions are in [`findings/`](findings/); issue and PR texts in [`upstream-fixes/README.md`](upstream-fixes/README.md).

## Add your framework

A typical adapter is 100 to 200 lines. Start from the one-file example, then check it:

```bash
cp examples/toy_adapter.py tracegap/adapters/myframework_adapters.py   # replace the toy framework with yours, rename the class
python -m tracegap.check_adapter tracegap.adapters.myframework_adapters:MyFrameworkCallbacks
```

The checker confirms the adapter's structure, that the calibration scenario passes in both modes, that nothing raises, and that verdicts are deterministic. Remaining failures are findings about the framework. The full guide is [**docs/ADD_YOUR_FRAMEWORK.md**](docs/ADD_YOUR_FRAMEWORK.md), and the pull request template asks for the checker output. You can also run your adapter without forking: `tracegap --adapter-module mypkg.tracegap_adapter:MyAdapter`.

Observability vendors: `tracegap.collectors` reads tool spans in both the OpenTelemetry GenAI conventions (`execute_tool`) and OpenInference (`TOOL` spans), so any instrumented framework can be measured with only the code that drives it.

## Dataset

About 11,500 labeled cases on Hugging Face ([`pushkardg/tracegap`](https://huggingface.co/datasets/pushkardg/tracegap); built into [`hf-dataset/`](hf-dataset/) by `scripts/build_dataset.py`). Each case has three aligned logs: the calls the model emitted, the **execution ledger** written by the tools themselves, and the **trace the framework recorded**, with labels and the reason for every failure. Splits: `current` (latest releases, core and generated suites) and `history` (65 past releases).

A second configuration, `tasks`, packages the corpus as four learning tasks (T1–T4), plus an adapter task (T5) scored by the benchmark, with the ledger hidden and whole frameworks held out for testing:

| Task | Predict from the emitted calls and the recorded trace |
|---|---|
| T1 Completeness detection | is the trace complete? |
| T2 Fidelity detection | are arguments, outputs and errors exact? |
| T3 Defect classification | which of 10 defect types are present? |
| T4 Execution reconstruction | what really happened to each emitted call (ok, error, cancelled, running, not executed)? |
| T5 Trace normalization | convert a framework's native trace into the canonical record (scored by the benchmark: write an adapter) |

```bash
python -m tracegap.tasks baselines --split test       # majority and rule-based baselines
python -m tracegap.tasks evaluate predictions.jsonl   # score your method
```

Baselines and the task definitions are in the [dataset card](hf-dataset/README.md); the datasheet is [`DATASHEET.md`](DATASHEET.md).

## Paper

**TraceGap: Measuring Whether LLM Agent Frameworks Record the Tool Calls Their Agents Make.** Pushkar Devanahalli Gopalakrishna. Preprint: [`paper/tmlr/tracegap_preprint.pdf`](paper/tmlr/tracegap_preprint.pdf) (see [`paper/README.md`](paper/README.md)). The prior-art search behind the novelty claim is in [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md).

```bibtex
@misc{gopalakrishna2026tracegap,
  title  = {TraceGap: Measuring Whether {LLM} Agent Frameworks Record the Tool Calls Their Agents Make},
  author = {Gopalakrishna, Pushkar Devanahalli},
  year   = {2026},
  doi    = {10.5281/zenodo.23324532},
  url    = {https://github.com/pushkardg/tracegap}
}
```

Or use [`CITATION.cff`](CITATION.cff) (GitHub's "Cite this repository" button). Cite the Zenodo concept DOI for the benchmark in general, or a version DOI for exact reproducibility.

## How it works

Each case produces two logs that do not depend on the framework, and compares them with the framework's trace:

| Source | What it holds | Written by |
|---|---|---|
| Emission log | every tool call the model asked for | the scripted model |
| Execution ledger | every tool call that actually started, with real arguments and outcome (ok, error, cancelled, running) | the tool body itself |
| Recorded trace | what the framework says happened | the framework's trace surface, read through an adapter |

Every tool takes a unique `tag` argument, so recorded events are matched to ground truth without trusting framework-assigned ids; surfaces that do not record arguments are matched by call id. A case where the model never emitted a call is a harness error, never a pass. If a framework asks the model for a tool-less final answer, the scripted model answers in text, as a real model would.

**Checked against itself.** A ~100-line reference agent loop is complete and faithful on every case, and eleven injected recording defects are each caught by the scenario designed for them, on the intended axis.

**Tiers.** A scenario is in the Stress tier when a tool raises inside a batch of parallel calls; everything else is Stable. The rule is structural, so the tier of any scenario is known before it runs. Core verdicts were identical across four full runs; generated-suite verdicts that differed between runs all fall in the Stress tier ([`results/generated/STABILITY.md`](results/generated/STABILITY.md), [`tracegap/tiers.py`](tracegap/tiers.py)).

### Trace surfaces

| Key | What is read |
|---|---|
| `langgraph/callbacks` | LangChain `on_tool_start/end/error` callbacks |
| `openai-agents/tracing` | `FunctionSpanData` spans via a `TracingProcessor` |
| `pydantic-ai/history`, `pydantic-ai/otel` | `capture_run_messages()` / `run_stream_events()`; `execute_tool` spans |
| `autogen/messages`, `autogen/otel` | `ToolCallRequest/ExecutionEvent` from `run()` / `run_stream()`; autogen-core `execute_tool` spans (name and call id only) |
| `smolagents/memory`, `smolagents/openinference` | `agent.memory.steps` (presence, args and call ids only); OpenInference TOOL spans |
| `llamaindex/events`, `llamaindex/openinference` | `ToolCall` / `ToolCallResult` workflow events; OpenInference TOOL spans |
| `semantic-kernel/filters`, `semantic-kernel/otel` | a FUNCTION_INVOCATION filter; SK GenAI diagnostics spans |
| `google-adk/events`, `google-adk/otel` | `Runner.run_async` events; ADK `execute_tool` spans |
| `crewai/events` | `ToolUsageStarted/Finished/Error` on the CrewAI event bus |

Each surface declares which fields it captures (`Capture(args, output, status, call_id)`) and is scored only on those.

### Reproducing everything

Frameworks have conflicting dependencies, so the full matrix runs each in its own pinned environment:

```bash
scripts/run_all.sh                       # core suite, all 9 frameworks; writes results/ and site/
SUITE=generated scripts/run_all.sh       # generated suite (n=200, seed=1)
python scripts/run_versions.py           # version history (uses uv; resolves deps as of each release)
python scripts/build_dataset.py          # Hugging Face dataset and tasks in hf-dataset/ (needs the traces from the runs above)
python scripts/update_readme.py          # refresh the table above
```

Running these overwrites the released results in `results/` and `hf-dataset/`. The released Parquet files are the canonical corpus; raw traces of the generated suite and of the version history are not in git. The paper's analyses and build are described in [`analysis/README.md`](analysis/README.md) and [`paper/README.md`](paper/README.md); `results/` file inventory is in [`DATASHEET.md`](DATASHEET.md).

## Limitations

- **Python only.** TypeScript and other-language SDKs are not covered.
- **Scripted models** exercise framework logic, not provider clients, so bugs in a specific provider integration won't appear.
- **Uniform cancellation** with `asyncio.Task.cancel()`, the mechanism behind timeouts and dropped requests. AutoGen's token path is covered by a separate reproduction.
- **Attempt visibility is judged at the tool layer.** A call visible only in raw model output does not count.
- **CrewAI's events are attributed to runs by task id**, so the isolation checks are lenient for that surface.
- **Results apply to the pinned versions.** Rerun before citing numbers for newer releases.

## Contributing

New adapters, scenarios and verdict disputes are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md), [docs/ADD_YOUR_FRAMEWORK.md](docs/ADD_YOUR_FRAMEWORK.md) and the issue templates.

## License

Code: MIT. Scenarios, results and the trace corpus: CC BY 4.0. See [LICENSE](LICENSE) and [DATASHEET.md](DATASHEET.md).
# tracegap-temp
