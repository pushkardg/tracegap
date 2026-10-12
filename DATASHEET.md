# Datasheet for TraceGap v1.0.0

Structured after *Datasheets for Datasets* (Gebru et al.).

## Motivation

**Why was it created?** To measure whether LLM agent frameworks record the tool calls their agents make completely and accurately. Existing agent benchmarks evaluate models (tool choice, task success). They do not evaluate the trace that frameworks produce, which observability, audit and evaluation pipelines depend on.

**Who created it?** Pushkar Devanahalli Gopalakrishna. The benchmark software, the experiments and an initial draft of the paper were developed with substantial assistance from Claude (Anthropic); the author directed the work and reviewed and verified the results. All results were produced by running the released code.

**Funding.** None.

## Composition

1. **Scenario suites.**
   - 22 hand-written scenarios in 7 categories (basic, failure, rejected, identity, payload, interrupt, structure), listed in `data/scenarios.json`.
   - A seeded generator (`tracegap/generator.py`). The released generated suite is n=200, seed=1. The same (n, seed) always yields the same scenarios.
   - Every scenario runs in two modes (invoke and stream).
2. **Results.** One record per (surface, scenario, mode) case, holding the two labels and every counter and failure reason. Files: `results/results.json` (core, 660 cases), `results/generated/results.json` (6,000 cases) and `results/versions/<framework>/<version>.json` (version history).
3. **Labeled trace corpus.** For every case, three aligned logs:
   - `emissions`: the calls the scripted model emitted.
   - `ledger`: the calls that started, with real arguments, final status (`ok`, `error`, `cancelled` or `running`), output and error.
   - `recorded`: what the framework's trace surface reported, normalized.

   Files: the Parquet files in `hf-dataset/data/` are the canonical corpus, with two splits:
   - `current`: latest versions, core plus generated suite, 6,660 rows.
   - `history`: core suite across 65 framework releases, 4,884 rows.

   The raw JSONL traces of the core suite are also in `results/traces/`. Raw traces of the generated suite and of the version history are not kept in git (they are large); rerunning `scripts/run_all.sh` and `scripts/run_versions.py` regenerates them.
4. **Learning tasks.** `hf-dataset/tasks/` holds the four tasks derived from the corpus (see below).
5. **Supporting files.**
   - `results/runs/run3.json`, `run4.json`: the last two of the four full core-suite runs (run4 is `results/results.json`). The first two predate the decision to keep run files.
   - `results/generated/runs/run1–3.json`: the three full generated-suite runs behind the stability claims (`results/generated/STABILITY.md`). Runs 1 and 2 were made with benchmark version 0.2.0; the scorer is unchanged since.
   - `results/generated/unstable_cases.json`: the 148 cases whose verdict differed between runs.
   - `results/seeds/seed2`, `seed3`: two further generated suites (n=100) used for ranking agreement in the paper.
   - `analysis/out/`: outputs of the paper's analyses (see `analysis/README.md`).

**Is it synthetic?** Yes. All data comes from running real framework code against scripted models and deterministic tools. There is no human data, no personal data, and no model-generated text other than fixed strings in the scenarios.

**Tasks.** A `tasks` configuration packages the cases as four learning tasks plus an adapter task (completeness detection, fidelity detection, defect classification, execution reconstruction, trace normalization) with the ledger hidden and whole frameworks held out: train (LangGraph, Pydantic AI, AutoGen, LlamaIndex, CrewAI; 5,884 examples), validation (OpenAI Agents SDK, Semantic Kernel; 2,344), test (Google ADK, smolagents; 2,832). Uncalibrated rows and harness errors are excluded. The harness's unique `tag` argument is removed from task inputs (and tag values echoed in outputs are replaced by a placeholder), so methods must join calls by call id as in production. Definitions, metrics and baselines: `tracegap/tasks.py` and the dataset card.

**Labels.** Ground truth comes from instrumentation, not annotation. The tools write the execution ledger themselves, independently of any framework's reporting.

**Known caveats.**
- **Uncalibrated rows.** `calibrated=false` marks rows where a surface fails the calibration case S01 for that framework version. Such rows mean the surface is absent in that version, or reports in a format the adapter does not read. 484 history rows are uncalibrated.
- **Excluded versions.** Some old versions could not be run at all and are excluded: LangGraph 0.4.10 (dependency mismatch), smolagents 1.14.0 (older API), CrewAI 1.6.1 and 1.8.1 (ReAct-only tool calling).
- **Fallback dependency resolution.** Four Semantic Kernel versions (1.30–1.36) were run with current dependency resolution, because their release-date dependency set no longer installs on Python 3.13. `results/versions/status.json` records the resolution used for every version.

## Collection process

Each case resets the ground-truth logs and builds a fresh agent with a scripted model. The run is executed, and cancelled at a fixed time where the scenario says so. Trace events are then read only through the framework's public observability interface. Any tool still running is drained before the next case starts.

Historical versions were installed with `uv --exclude-newer <release date + 1 day>`, so each run sees the dependencies users installed at the time.

Verdict stability:
- Core suite: identical across four full runs.
- Generated suite: three full runs agreed on 5,852 of 6,000 verdicts (97.5%). The other 148 are races inside Pydantic AI and LangGraph when a call in a parallel batch fails. They are flagged `stable=false`; see `results/generated/STABILITY.md`.
- Every unstable case is in the **Stress** tier (a tool raises inside a batch of parallel calls; `tracegap/tiers.py`). Stable-tier verdicts were identical in every run, so rankings use only Stable cases. The `tier` column marks each row.

Current framework versions are listed in `envs/*.txt`. Python 3.13.16.

## Uses

**Intended uses:**
- Comparing trace completeness across frameworks and releases.
- Regression-testing an observability layer.
- Testing trace validators, OpenTelemetry back ends and provenance tools against the labeled corpus.

**Not suitable for:**
- Evaluating model quality. The models are scripted.
- Making claims about framework versions not listed.
- Judging a framework overall. Some gaps are deliberate design choices.

## Distribution and maintenance

Distributed on GitHub, PyPI (`tracegap`), Hugging Face Datasets and Zenodo (a concept DOI for all versions and a DOI per release, added on publication). Code is MIT-licensed; data and results are CC BY 4.0. A weekly CI job runs the four core-environment frameworks at their latest releases and fails if a Stable-tier case regresses against the released results; the other five frameworks are re-run manually with `scripts/run_all.sh`. Results are versioned with the benchmark version.
