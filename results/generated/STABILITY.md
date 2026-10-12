# Verdict stability: generated(n=200, seed=1) suite

The suite (generated(n=200, seed=1); 6,000 cases) has been run in full 3 times. 5,852 of 6,000 verdicts (97.5%) were identical in every run; 148 differed in at least one.

Every case that differed is in the **Stress** tier (a tool raises inside a parallel batch)

| Surface | Cases that differed |
|---|---|
| pydantic-ai/history | 119 |
| pydantic-ai/otel | 18 |
| langgraph/callbacks | 11 |

Differing cases by run: runs 1-2: 104; run 3 added 44.

Benchmark version of each run: run1 0.2.0, run2 0.2.0, run3 1.0.0 (the scorer did not change between these versions).

What varies (from manual inspection of the generated-suite cases): in Pydantic AI, whether a sibling call that succeeded gets its result recorded (history) or its span exported with its result (OpenTelemetry) before the run aborts; in LangGraph, whether a sibling had started executing when the run aborted. These are races inside the frameworks, so the leaderboard ranks only the Stable tier and reports the Stress tier separately.

The published numbers are from the latest run. The cases are listed in `unstable_cases.json` and flagged `stable=false` in the Hugging Face dataset. Recompute with `python scripts/stability.py results/generated/runs/run1.json results/generated/runs/run2.json results/generated/runs/run3.json`.
