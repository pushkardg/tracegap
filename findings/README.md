# Findings: standalone reproductions

Each script depends only on the framework itself, not on TraceGap, so it can be attached directly to an upstream issue. All three were confirmed on 3 October 2026 with the pinned versions in `../envs/` (`core.txt` for the OpenAI Agents SDK and AutoGen).

| Script | Framework | Behaviour |
|---|---|---|
| `openai_agents_cancelled_tool_reported_ok.py` | OpenAI Agents SDK 0.23.1 | A tool interrupted by run cancellation ends its function span with no error and no output, so it is indistinguishable from success. |
| `autogen_task_cancel_orphaned_tool.py` | AutoGen 0.7.5 | Cancelling the task running `AssistantAgent.run()` does not stop an in-flight tool. The tool finishes later and keeps its side effects. |
| `autogen_token_cancel_deadlock.py` | AutoGen 0.7.5 | Cancelling through `CancellationToken` during a tool call stops the tool, but `run()` never returns. |

## Root causes (from reading the source)

- **OpenAI Agents SDK.** `SpanImpl.__exit__` in `agents/tracing/spans.py` ignores `exc_type`. The function-tool executor in `agents/run_internal/tool_execution.py` attaches span errors in an `except Exception` block, which does not catch `asyncio.CancelledError` (a `BaseException`). The span therefore closes as if the call succeeded.
- **AutoGen token deadlock.** In `AssistantAgent._process_model_result`, the inner `_execute_tool_calls` coroutine awaits `asyncio.gather(...)` and then calls `stream_queue.put_nowait(None)`. If a tool is cancelled, `gather` raises `CancelledError`, the sentinel is never queued, and the consumer loop `while True: await stream.get()` waits forever. Wrapping the gather in `try/finally` so the sentinel is always queued is a likely fix.

## Found during development (v0.2; fixes in `../upstream-fixes/`)

| Framework | Behaviour | How to see it |
|---|---|---|
| Semantic Kernel 1.44.1 | A cancelled kernel function's `execute_tool` span has an unset (successful-looking) status | TraceGap S17, `semantic-kernel/otel`; regression test in the patch |
| Google ADK 2.11.0 | A cancelled tool's `execute_tool` span is unset, including siblings ADK cancels after one parallel call fails | TraceGap S07 and S17, `google-adk/otel` |
| AutoGen 0.7.5 | Once the orphaned-tool bug is fixed, the cancelled tool's span is unset (`trace_tool_span` handles only `Exception`) | regression test in the patch |
| smolagents 1.26.0 | A step's memory records no tool calls when any call in it fails; calls with duplicate ids are silently dropped | TraceGap S05–S07 and S11, `smolagents/memory` |

The common cause of the cancellation spans: OpenTelemetry's `use_span` records only `Exception`, and `asyncio.CancelledError` is a `BaseException`.

## Before filing upstream

Quick searches on 3–4 October 2026 found no existing report of these defects. One related decision exists: openai-agents-python #4073/#4191 deliberately keep `CancelledError` from marking the *agent* span. The OpenAI issue and PR texts address that directly. Search each project's issue tracker for "cancel" and "span" (or "CancellationToken") before filing, and link any existing issue instead of opening a duplicate. When filing, include the script, the version, and a link to the TraceGap scenario that found it (S17).
