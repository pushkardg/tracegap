TraceGap measures whether LLM agent frameworks record the tool calls their agents make. Scripted models drive 9 frameworks (15 trace surfaces) through fault scenarios: tool failures, cancellation, parallel calls, rejected calls and nested agents. Each framework's own trace is compared with ground truth that does not depend on the framework.

**In this release**
- Benchmark software (`pip install tracegap`), 22 hand-written scenarios and a seeded scenario generator
- Adapters for 9 frameworks and 15 trace surfaces; Stable and Stress tiers
- Results for current releases and 65 past releases (`results/`)
- A labeled corpus of about 11,500 cases, with four learning tasks (T1–T4) plus an adapter task (T5) and baselines (`hf-dataset/`)
- Fixes with regression tests for defects found in five frameworks (`upstream-fixes/`)
- The paper preprint (attached)

Code is MIT-licensed. Scenarios, results and the corpus are CC BY 4.0. See `CITATION.cff` to cite.
