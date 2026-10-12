# TraceGap version history

Core suite (22 scenarios x 2 modes) run against 65 released versions of 9 frameworks. Each version's dependencies were resolved as of one day after its release where that still installs; see results/versions/status.json for the resolution used per version.

Not covered: crewai==1.6.1, crewai==1.8.1, langgraph==0.4.10, smolagents==1.14.0.

Left out because the calibration case S01 (one successful call) fails, meaning the surface is absent in that version or reports in a format the current adapter does not read: autogen/otel 0.4.9.3, autogen/otel 0.5.3, autogen/otel 0.5.7, autogen/otel 0.6.1, semantic-kernel/otel 1.30.0, semantic-kernel/otel 1.32.2, semantic-kernel/otel 1.34.0, smolagents/openinference 1.16.1, smolagents/openinference 1.18.0, smolagents/openinference 1.20.0, smolagents/openinference 1.22.0.

## autogen/messages

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 0.7.5 | 2025-09-30 | 39/44 | 44/44 |
| 0.7.2 | 2025-08-07 | 39/44 | 44/44 |
| 0.6.4 | 2025-07-09 | 39/44 | 44/44 |
| 0.6.1 | 2025-06-05 | 42/44 | 44/44 |
| 0.5.7 | 2025-05-14 | 42/44 | 44/44 |
| 0.5.3 | 2025-04-17 | 42/44 | 44/44 |
| 0.4.9.3 | 2025-03-29 | 42/44 | 44/44 |

Verdict changes between consecutive versions:

- 0.6.1 -> 0.6.4: S17 invoke: complete, faithful -> incomplete, faithful (the framework ran the scenario differently: 1 -> 2 calls emitted, so this may not be a tracing change)
- 0.6.1 -> 0.6.4: S18 invoke: complete, faithful -> incomplete, faithful (the framework ran the scenario differently: 1 -> 2 calls emitted, so this may not be a tracing change)
- 0.6.1 -> 0.6.4: S19 invoke: complete, faithful -> incomplete, faithful (the framework ran the scenario differently: 1 -> 2 calls emitted, so this may not be a tracing change)

## autogen/otel

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 0.7.5 | 2025-09-30 | 40/44 | 44/44 |
| 0.7.2 | 2025-08-07 | 40/44 | 44/44 |
| 0.6.4 | 2025-07-09 | 40/44 | 44/44 |

No verdict changed across the versions tested.

## crewai/events

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.15.23 | 2026-09-28 | 44/44 | 44/44 |
| 1.14.7 | 2026-06-11 | 42/44 | 44/44 |
| 1.12.2 | 2026-03-26 | 42/44 | 44/44 |
| 1.10.1 | 2026-03-04 | 42/44 | 44/44 |

Verdict changes between consecutive versions:

- 1.14.7 -> 1.15.23: S08 invoke: incomplete, faithful -> complete, faithful
- 1.14.7 -> 1.15.23: S08 stream: incomplete, faithful -> complete, faithful

## google-adk/events

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 2.11.0 | 2026-10-02 | 44/44 | 36/44 |
| 2.9.2 | 2026-09-18 | 44/44 | 36/44 |
| 2.7.1 | 2026-08-17 | 44/44 | 36/44 |
| 2.5.0 | 2026-07-16 | 44/44 | 36/44 |
| 2.3.0 | 2026-06-18 | 44/44 | 36/44 |
| 2.0.0 | 2026-05-19 | 44/44 | 36/44 |
| 1.39.1 | 2026-08-27 | 44/44 | 36/44 |
| 1.35.2 | 2026-06-17 | 44/44 | 36/44 |

No verdict changed across the versions tested.

## google-adk/otel

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 2.11.0 | 2026-10-02 | 40/44 | 44/44 |
| 2.9.2 | 2026-09-18 | 40/44 | 44/44 |
| 2.7.1 | 2026-08-17 | 38/44 | 44/44 |
| 2.5.0 | 2026-07-16 | 36/44 | 44/44 |
| 2.3.0 | 2026-06-18 | 36/44 | 44/44 |
| 2.0.0 | 2026-05-19 | 36/44 | 44/44 |
| 1.39.1 | 2026-08-27 | 36/44 | 44/44 |
| 1.35.2 | 2026-06-17 | 36/44 | 44/44 |

Verdict changes between consecutive versions:

- 2.5.0 -> 2.7.1: S10 invoke: incomplete, faithful -> complete, faithful
- 2.5.0 -> 2.7.1: S10 stream: incomplete, faithful -> complete, faithful
- 2.7.1 -> 2.9.2: S08 invoke: incomplete, faithful -> complete, faithful
- 2.7.1 -> 2.9.2: S08 stream: incomplete, faithful -> complete, faithful

## langgraph/callbacks

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.2.12 | 2026-09-21 | 40/44 | 44/44 |
| 1.1.10 | 2026-04-27 | 40/44 | 44/44 |
| 1.0.10 | 2026-02-27 | 40/44 | 44/44 |
| 0.6.11 | 2025-10-21 | 40/44 | 44/44 |
| 0.5.4 | 2025-07-21 | 40/44 | 44/44 |

No verdict changed across the versions tested.

## llamaindex/events

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 0.14.25 | 2026-09-21 | 42/44 | 44/44 |
| 0.14.20 | 2026-04-03 | 42/44 | 44/44 |
| 0.14.15 | 2026-02-18 | 42/44 | 44/44 |
| 0.14.10 | 2025-12-04 | 42/44 | 44/44 |
| 0.14.5 | 2025-10-15 | 42/44 | 44/44 |
| 0.14.0 | 2025-09-08 | 42/44 | 44/44 |
| 0.13.6 | 2025-09-07 | 42/44 | 44/44 |
| 0.12.52 | 2025-07-22 | 42/44 | 44/44 |

No verdict changed across the versions tested.

## llamaindex/openinference

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 0.14.25 | 2026-09-21 | 38/44 | 44/44 |
| 0.14.20 | 2026-04-03 | 38/44 | 44/44 |
| 0.14.15 | 2026-02-18 | 38/44 | 44/44 |
| 0.14.10 | 2025-12-04 | 38/44 | 44/44 |
| 0.14.5 | 2025-10-15 | 38/44 | 44/44 |
| 0.14.0 | 2025-09-08 | 38/44 | 44/44 |
| 0.13.6 | 2025-09-07 | 38/44 | 44/44 |
| 0.12.52 | 2025-07-22 | 38/44 | 44/44 |

No verdict changed across the versions tested.

## openai-agents/tracing

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 0.23.1 | 2026-10-02 | 38/44 | 38/44 |
| 0.22.3 | 2026-09-17 | 38/44 | 44/44 |
| 0.21.1 | 2026-08-16 | 38/44 | 44/44 |
| 0.20.0 | 2026-08-11 | 38/44 | 44/44 |
| 0.19.4 | 2026-08-05 | 40/44 | 44/44 |
| 0.18.3 | 2026-07-17 | 40/44 | 44/44 |
| 0.17.8 | 2026-07-06 | 40/44 | 44/44 |
| 0.16.1 | 2026-05-07 | 40/44 | 44/44 |
| 0.15.3 | 2026-05-06 | 40/44 | 44/44 |
| 0.14.8 | 2026-04-29 | 40/44 | 44/44 |

Verdict changes between consecutive versions:

- 0.19.4 -> 0.20.0: S11 invoke: complete, faithful -> incomplete, faithful
- 0.19.4 -> 0.20.0: S11 stream: complete, faithful -> incomplete, faithful
- 0.22.3 -> 0.23.1: S05 invoke: complete, faithful -> complete, unfaithful
- 0.22.3 -> 0.23.1: S05 stream: complete, faithful -> complete, unfaithful
- 0.22.3 -> 0.23.1: S06 invoke: complete, faithful -> complete, unfaithful
- 0.22.3 -> 0.23.1: S06 stream: complete, faithful -> complete, unfaithful
- 0.22.3 -> 0.23.1: S07 invoke: complete, faithful -> complete, unfaithful
- 0.22.3 -> 0.23.1: S07 stream: complete, faithful -> complete, unfaithful

## pydantic-ai/history

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 2.54.0 | 2026-10-03 | 41/44 | 38/44 |
| 2.50.0 | 2026-09-25 | 40/44 | 36/44 |
| 2.45.0 | 2026-09-18 | 40/44 | 36/44 |
| 2.40.0 | 2026-09-05 | 40/44 | 36/44 |
| 2.35.3 | 2026-08-28 | 40/44 | 36/44 |
| 2.30.0 | 2026-08-14 | 40/44 | 36/44 |
| 2.25.0 | 2026-08-06 | 40/44 | 36/44 |
| 2.20.0 | 2026-07-29 | 40/44 | 36/44 |
| 2.15.0 | 2026-07-22 | 40/44 | 36/44 |

Verdict changes between consecutive versions:

- 2.50.0 -> 2.54.0: S11 invoke: incomplete, unfaithful -> complete, faithful (the framework ran the scenario differently: 3 -> 2 calls emitted, so this may not be a tracing change)
- 2.50.0 -> 2.54.0: S11 stream: incomplete, unfaithful -> incomplete, faithful (the framework ran the scenario differently: 3 -> 2 calls emitted, so this may not be a tracing change)

## pydantic-ai/otel

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 2.54.0 | 2026-10-03 | 40/44 | 44/44 |
| 2.50.0 | 2026-09-25 | 40/44 | 44/44 |
| 2.45.0 | 2026-09-18 | 40/44 | 44/44 |
| 2.40.0 | 2026-09-05 | 40/44 | 44/44 |
| 2.35.3 | 2026-08-28 | 40/44 | 44/44 |
| 2.30.0 | 2026-08-14 | 40/44 | 44/44 |
| 2.25.0 | 2026-08-06 | 36/44 | 44/44 |
| 2.20.0 | 2026-07-29 | 36/44 | 44/44 |
| 2.15.0 | 2026-07-22 | 36/44 | 44/44 |

Verdict changes between consecutive versions:

- 2.25.0 -> 2.30.0: S09 invoke: incomplete, faithful -> complete, faithful
- 2.25.0 -> 2.30.0: S09 stream: incomplete, faithful -> complete, faithful
- 2.25.0 -> 2.30.0: S10 invoke: incomplete, faithful -> complete, faithful
- 2.25.0 -> 2.30.0: S10 stream: incomplete, faithful -> complete, faithful

## semantic-kernel/filters

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.44.1 | 2026-08-06 | 40/44 | 44/44 |
| 1.42.0 | 2026-05-14 | 40/44 | 44/44 |
| 1.40.0 | 2026-03-02 | 40/44 | 44/44 |
| 1.38.0 | 2025-11-11 | 40/44 | 44/44 |
| 1.36.2 | 2025-09-04 | 40/44 | 44/44 |
| 1.34.0 | 2025-06-25 | 40/44 | 44/44 |
| 1.32.2 | 2025-06-04 | 40/44 | 44/44 |
| 1.30.0 | 2025-05-15 | 40/44 | 44/44 |

No verdict changed across the versions tested.

## semantic-kernel/otel

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.44.1 | 2026-08-06 | 38/44 | 44/44 |
| 1.42.0 | 2026-05-14 | 38/44 | 44/44 |
| 1.40.0 | 2026-03-02 | 38/44 | 44/44 |
| 1.38.0 | 2025-11-11 | 38/44 | 44/44 |
| 1.36.2 | 2025-09-04 | 38/44 | 44/44 |

No verdict changed across the versions tested.

## smolagents/memory

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.26.0 | 2026-05-29 | 28/44 | 44/44 |
| 1.24.0 | 2026-01-16 | 28/44 | 44/44 |
| 1.22.0 | 2025-09-25 | 28/44 | 44/44 |
| 1.20.0 | 2025-07-10 | 28/44 | 44/44 |
| 1.18.0 | 2025-06-10 | 30/44 | 44/44 |
| 1.16.1 | 2025-05-16 | 36/44 | 44/44 |

Verdict changes between consecutive versions:

- 1.16.1 -> 1.18.0: S03 invoke: incomplete, faithful -> complete, faithful
- 1.16.1 -> 1.18.0: S03 stream: incomplete, faithful -> complete, faithful
- 1.16.1 -> 1.18.0: S05 invoke: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S05 stream: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S06 invoke: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S06 stream: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S08 invoke: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S08 stream: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S09 invoke: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S09 stream: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S10 invoke: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S10 stream: complete, faithful -> incomplete, faithful
- 1.16.1 -> 1.18.0: S11 invoke: incomplete, faithful -> complete, faithful
- 1.16.1 -> 1.18.0: S11 stream: incomplete, faithful -> complete, faithful
- 1.18.0 -> 1.20.0: S11 invoke: complete, faithful -> incomplete, faithful
- 1.18.0 -> 1.20.0: S11 stream: complete, faithful -> incomplete, faithful

## smolagents/openinference

| Version | Released | Complete | Faithful |
|---|---|---|---|
| 1.26.0 | 2026-05-29 | 34/44 | 44/44 |
| 1.24.0 | 2026-01-16 | 34/44 | 44/44 |

No verdict changed across the versions tested.

