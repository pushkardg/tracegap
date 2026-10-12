# TraceGap 1.0.0 results

Generated 2026-10-04T04:06:27+00:00 on Python 3.13.16. 22 scenarios x 2 modes = 44 cases per surface.

## Leaderboard

| Framework / surface | Complete | Faithful | Executed calls recorded | Status correct | Failed calls shown as success | Unexecuted attempts visible | Args exact | Output/error exact |
|---|---|---|---|---|---|---|---|---|
| crewai/events | 44/44 | 44/44 | 100.0% | 100.0% | 0 | 6/6 | 100.0% | 100.0% |
| google-adk/events | 44/44 | 36/44 | 100.0% | 100.0% | 0 | 4/4 | 100.0% | 93.3% |
| llamaindex/events | 42/44 | 44/44 | 100.0% | 100.0% | 0 | 4/6 | 100.0% | 100.0% |
| pydantic-ai/history | 41/44 | 38/44 | 96.7% | 100.0% | 0 | 8/10 | 100.0% | 94.5% |
| autogen/otel | 40/44 | 44/44 | 98.4% | 100.0% | 0 | 4/6 | n/a | n/a |
| google-adk/otel | 40/44 | 44/44 | 100.0% | 95.2% | 6 | 4/4 | 100.0% | 100.0% |
| langgraph/callbacks | 40/44 | 44/44 | 100.0% | 100.0% | 0 | 4/8 | 100.0% | 100.0% |
| pydantic-ai/otel | 40/44 | 44/44 | 100.0% | 100.0% | 0 | 4/10 | 100.0% | 100.0% |
| semantic-kernel/filters | 40/44 | 44/44 | 100.0% | 100.0% | 0 | 2/6 | 100.0% | 100.0% |
| autogen/messages | 39/44 | 44/44 | 92.1% | 100.0% | 0 | 6/6 | 100.0% | 100.0% |
| llamaindex/openinference | 38/44 | 44/44 | 98.4% | 100.0% | 0 | 2/6 | 100.0% | 100.0% |
| semantic-kernel/otel | 38/44 | 44/44 | 100.0% | 98.4% | 2 | 2/6 | 100.0% | 100.0% |
| openai-agents/tracing | 38/44 | 38/44 | 100.0% | 98.4% | 2 | 4/10 | 100.0% | 95.0% |
| smolagents/openinference | 34/44 | 44/44 | 98.4% | 100.0% | 0 | 0/8 | 100.0% | 100.0% |
| smolagents/memory | 28/44 | 44/44 | 90.3% | n/a | 0 | 0/8 | 100.0% | n/a |

Complete = every call present with an honest status, no phantoms or duplicates, runs neither mixed nor fragmented. Faithful = every captured argument, output and error message exact. n/a = the surface does not capture that field.

## Scenario matrix

C = complete, F = faithful, `-` = failed. Left of the slash is invoke mode, right is stream mode.

| Scenario | crewai/events | google-adk/events | llamaindex/events | pydantic-ai/history | autogen/otel | google-adk/otel | langgraph/callbacks | pydantic-ai/otel | semantic-kernel/filters | autogen/messages | llamaindex/openinference | semantic-kernel/otel | openai-agents/tracing | smolagents/openinference | smolagents/memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 Single call | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S02 Sequential calls | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S03 Parallel calls | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S04 Long session | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S05 Tool raises | CF/CF | C-/C- | CF/CF | C-/C- | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | C-/C- | CF/CF | -F/-F |
| S06 Failure then retry | CF/CF | C-/C- | CF/CF | C-/C- | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | C-/C- | CF/CF | -F/-F |
| S07 Parallel batch with one failure | CF/CF | C-/C- | CF/CF | C-/C- | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | C-/C- | CF/CF | -F/-F |
| S08 Unknown tool | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | -F/-F | -F/-F | -F/-F | CF/CF | -F/-F | -F/-F | -F/-F | -F/-F | -F/-F |
| S09 Invalid argument type | CF/CF | C-/C- | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | -F/-F |
| S10 Missing required argument | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | -F/-F | CF/CF | -F/-F | -F/-F |
| S11 Duplicate call ids | CF/CF | CF/CF | CF/CF | CF/-F | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | -F/-F | -F/-F |
| S12 Unicode and escape characters | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S13 Large output | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S14 Structured output | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S15 None output | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S16 Synchronous tool | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S17 Cancelled during a tool | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | -F/-F | CF/CF | CF/CF | CF/CF | -F/CF | -F/-F | -F/-F | -F/-F | -F/-F | -F/-F |
| S18 Cancelled after tools completed | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | -F/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S19 Model error after tools | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | -F/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S20 Turn limit exceeded | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | CF/CF |
| S21 Concurrent runs | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |
| S22 Nested agent as tool | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF | -F/-F | CF/CF | CF/CF | CF/CF | CF/CF | CF/CF |

## Every failure

### google-adk/events

- S05 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S05 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S06 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S06 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S07 invoke: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S07 stream: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S09 invoke: fidelity: t1: error message not recorded (actual='TypeError: can only concatenate str (not "int") to str')
- S09 stream: fidelity: t1: error message not recorded (actual='TypeError: can only concatenate str (not "int") to str')

### llamaindex/events

- S20 invoke: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace
- S20 stream: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace

### pydantic-ai/history

- S05 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S05 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S06 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S06 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S07 invoke: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S07 stream: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S11 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t2: emitted but never executed, and the attempt is invisible in the trace
- S22 invoke: **completeness**: n1: executed (ok) but missing from trace
- S22 invoke: **completeness**: n2: executed (ok) but missing from trace
- S22 stream: **completeness**: n1: executed (ok) but missing from trace
- S22 stream: **completeness**: n2: executed (ok) but missing from trace

### autogen/otel

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: executed (running) but missing from trace
- S17 stream: **completeness**: t2: executed (running) but missing from trace

### google-adk/otel

- S07 invoke: **completeness**: t1: actual=cancelled but trace status=ok
- S07 invoke: **completeness**: t3: actual=cancelled but trace status=ok
- S07 stream: **completeness**: t1: actual=cancelled but trace status=ok
- S07 stream: **completeness**: t3: actual=cancelled but trace status=ok
- S17 invoke: **completeness**: t2: actual=cancelled but trace status=ok
- S17 stream: **completeness**: t2: actual=cancelled but trace status=ok

### langgraph/callbacks

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S20 invoke: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace
- S20 stream: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace

### pydantic-ai/otel

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t2: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t2: emitted but never executed, and the attempt is invisible in the trace

### semantic-kernel/filters

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace

### autogen/messages

- S17 invoke: **completeness**: t1: executed (ok) but missing from trace
- S17 invoke: **completeness**: t2: executed (running) but missing from trace
- S18 invoke: **completeness**: t1: executed (ok) but missing from trace
- S18 invoke: **completeness**: t2: executed (ok) but missing from trace
- S19 invoke: **completeness**: t1: executed (ok) but missing from trace
- S19 invoke: **completeness**: t2: executed (ok) but missing from trace
- S22 invoke: **completeness**: n1: executed (ok) but missing from trace
- S22 invoke: **completeness**: n2: executed (ok) but missing from trace
- S22 stream: **completeness**: n1: executed (ok) but missing from trace
- S22 stream: **completeness**: n2: executed (ok) but missing from trace

### llamaindex/openinference

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: executed (running) but missing from trace
- S17 stream: **completeness**: t2: executed (running) but missing from trace
- S20 invoke: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace
- S20 stream: **completeness**: t3: emitted but never executed, and the attempt is invisible in the trace

### semantic-kernel/otel

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: actual=cancelled but trace status=ok
- S17 stream: **completeness**: t2: actual=cancelled but trace status=ok

### openai-agents/tracing

- S05 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S05 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: disk full')
- S06 invoke: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S06 stream: fidelity: t1: error message not recorded (actual='ToolFailure: tool failed: transient')
- S07 invoke: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S07 stream: fidelity: t2: error message not recorded (actual='ToolFailure: tool failed: boom')
- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t2: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t2: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: actual=cancelled but trace status=ok
- S17 stream: **completeness**: t2: actual=cancelled but trace status=ok

### smolagents/openinference

- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S09 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S09 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: executed (running) but missing from trace
- S17 stream: **completeness**: t2: executed (running) but missing from trace

### smolagents/memory

- S05 invoke: **completeness**: t1: executed (error) but missing from trace
- S05 stream: **completeness**: t1: executed (error) but missing from trace
- S06 invoke: **completeness**: t1: executed (error) but missing from trace
- S06 stream: **completeness**: t1: executed (error) but missing from trace
- S07 invoke: **completeness**: t1: executed (ok) but missing from trace
- S07 invoke: **completeness**: t2: executed (error) but missing from trace
- S07 invoke: **completeness**: t3: executed (ok) but missing from trace
- S07 stream: **completeness**: t1: executed (ok) but missing from trace
- S07 stream: **completeness**: t2: executed (error) but missing from trace
- S07 stream: **completeness**: t3: executed (ok) but missing from trace
- S08 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S08 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S09 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S09 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S10 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 invoke: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S11 stream: **completeness**: t1: emitted but never executed, and the attempt is invisible in the trace
- S17 invoke: **completeness**: t2: executed (running) but missing from trace
- S17 stream: **completeness**: t2: executed (running) but missing from trace

## Tools still running after the run ended (informational)

- autogen/messages S17 invoke
- autogen/messages S17 stream
- autogen/otel S17 invoke
- autogen/otel S17 stream
- smolagents/memory S17 invoke
- smolagents/memory S17 stream
- smolagents/openinference S17 invoke
- smolagents/openinference S17 stream
- llamaindex/events S17 invoke
- llamaindex/events S17 stream
- llamaindex/openinference S17 invoke
- llamaindex/openinference S17 stream
- crewai/events S17 invoke
- crewai/events S17 stream

## Versions

- autogen/messages: autogen-agentchat 0.7.5, autogen-core 0.7.5
- autogen/otel: autogen-agentchat 0.7.5, autogen-core 0.7.5
- langgraph/callbacks: langgraph 1.2.12, langchain-core 1.6.6
- openai-agents/tracing: openai-agents 0.23.1
- pydantic-ai/history: pydantic-ai-slim 2.54.0
- pydantic-ai/otel: pydantic-ai-slim 2.54.0
- smolagents/memory: smolagents 1.26.0
- smolagents/openinference: smolagents 1.26.0
- llamaindex/events: llama-index-core 0.14.25
- llamaindex/openinference: llama-index-core 0.14.25
- semantic-kernel/filters: semantic-kernel 1.44.1
- semantic-kernel/otel: semantic-kernel 1.44.1
- google-adk/events: google-adk 2.11.0
- google-adk/otel: google-adk 2.11.0
- crewai/events: crewai 1.15.23
