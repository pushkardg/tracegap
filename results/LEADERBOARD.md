# TraceGap agent trace reliability leaderboard

Benchmark 1.0.0. Primary ranking uses **Stable** cases only: scenarios whose verdicts were identical across repeated full runs, so your score does not change when you run it again. **Stress** cases (a tool raising inside a parallel batch) are reported separately because some frameworks handle them with scheduling-dependent races. See `tracegap/tiers.py`.

Stable: 2304 of 3090 cases complete (74.6%). Stress: 2028 of 3570 (56.8%).

## Stable tier

| # | Framework / surface | Version | Complete | Faithful | Tool failures | Cancellation | Rejected calls | Nested agents |
|---|---|---|---|---|---|---|---|---|
| 1 | crewai/events | crewai 1.15.23 | 206/206 (100.0%) | 206/206 (100.0%) | 4/4 | 4/4 | 6/6 | 2/2 |
| 2 | google-adk/otel | google-adk 2.11.0 | 190/206 (92.2%) | 206/206 (100.0%) | 4/4 | 2/4 | 6/6 | 2/2 |
| 3 | llamaindex/events | llama-index-core 0.14.25 | 188/206 (91.3%) | 206/206 (100.0%) | 4/4 | 4/4 | 6/6 | 2/2 |
| 4 | pydantic-ai/history | pydantic-ai-slim 2.54.0 | 185/206 (89.8%) | 186/206 (90.3%) | 4/4 | 4/4 | 6/6 | 0/2 |
| 5 | pydantic-ai/otel | pydantic-ai-slim 2.54.0 | 166/206 (80.6%) | 206/206 (100.0%) | 4/4 | 4/4 | 4/6 | 2/2 |
| 6 | autogen/otel | autogen-agentchat 0.7.5 | 160/206 (77.7%) | 206/206 (100.0%) | 4/4 | 2/4 | 4/6 | 2/2 |
| 7 | langgraph/callbacks | langgraph 1.2.12 | 160/206 (77.7%) | 206/206 (100.0%) | 4/4 | 4/4 | 4/6 | 2/2 |
| 8 | google-adk/events | google-adk 2.11.0 | 160/206 (77.7%) | 136/206 (66.0%) | 4/4 | 4/4 | 6/6 | 2/2 |
| 9 | openai-agents/tracing | openai-agents 0.23.1 | 158/206 (76.7%) | 186/206 (90.3%) | 4/4 | 2/4 | 4/6 | 2/2 |
| 10 | autogen/messages | autogen-agentchat 0.7.5 | 153/206 (74.3%) | 206/206 (100.0%) | 4/4 | 2/4 | 6/6 | 0/2 |
| 11 | llamaindex/openinference | llama-index-core 0.14.25 | 144/206 (69.9%) | 206/206 (100.0%) | 4/4 | 2/4 | 4/6 | 2/2 |
| 12 | semantic-kernel/filters | semantic-kernel 1.44.1 | 138/206 (67.0%) | 206/206 (100.0%) | 4/4 | 4/4 | 2/6 | 2/2 |
| 13 | semantic-kernel/otel | semantic-kernel 1.44.1 | 124/206 (60.2%) | 206/206 (100.0%) | 4/4 | 2/4 | 2/6 | 2/2 |
| 14 | smolagents/openinference | smolagents 1.26.0 | 92/206 (44.7%) | 206/206 (100.0%) | 4/4 | 2/4 | 0/6 | 2/2 |
| 15 | smolagents/memory | smolagents 1.26.0 | 80/206 (38.8%) | 206/206 (100.0%) | 0/4 | 2/4 | 0/6 | 2/2 |

Complete: every call present with an honest status, no phantoms or duplicates, runs neither mixed nor fragmented. Faithful: every captured argument, output and error message exact. Capability columns count complete Stable cases among the scenarios that test it: tool failures S05–S06, cancellation S17–S18, rejected calls S08–S10, nested agents S22 (each in invoke and stream mode).

## Stress tier

| Framework / surface | Complete | Faithful |
|---|---|---|
| crewai/events | 238/238 (100.0%) | 238/238 (100.0%) |
| google-adk/otel | 236/238 (99.2%) | 238/238 (100.0%) |
| llamaindex/events | 196/238 (82.4%) | 238/238 (100.0%) |
| pydantic-ai/history | 115/238 (48.3%) | 20/238 (8.4%) |
| pydantic-ai/otel | 184/238 (77.3%) | 232/238 (97.5%) |
| autogen/otel | 148/238 (62.2%) | 238/238 (100.0%) |
| langgraph/callbacks | 142/238 (59.7%) | 238/238 (100.0%) |
| google-adk/events | 34/238 (14.3%) | 18/238 (7.6%) |
| openai-agents/tracing | 148/238 (62.2%) | 54/238 (22.7%) |
| autogen/messages | 177/238 (74.4%) | 238/238 (100.0%) |
| llamaindex/openinference | 114/238 (47.9%) | 238/238 (100.0%) |
| semantic-kernel/filters | 116/238 (48.7%) | 238/238 (100.0%) |
| semantic-kernel/otel | 96/238 (40.3%) | 238/238 (100.0%) |
| smolagents/openinference | 70/238 (29.4%) | 238/238 (100.0%) |
| smolagents/memory | 14/238 (5.9%) | 238/238 (100.0%) |

Per-suite detail, scenario matrix and every failure reason: `results/CORE.md` and `results/generated/LEADERBOARD.md`.
