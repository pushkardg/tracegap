# Upstream fixes

Five patches for defects TraceGap found. Each was checked in two ways:

1. **The project's own tests.** The new regression test fails on current `main` and passes with the fix, and the surrounding suite shows no new failures.
2. **TraceGap.** The affected scenarios fail with the released version and pass with the patched version.

All five were prepared on 3–4 October 2026 against each project's `main`.

| Patch | Project (base) | Fixes | TraceGap scenarios fixed |
|---|---|---|---|
| `openai-agents-cancelled-tool-span.patch` | openai-agents-python `81f0ccf` (0.23.1) | A cancelled function tool closes its span with no error | S17 |
| `autogen-assistant-agent-tool-cancellation.patch` | autogen `027ecf0` (0.7.5) | (a) `run()` hangs after a `CancellationToken` cancel during a tool; (b) an in-flight tool keeps running after the run task is cancelled; (c) `trace_tool_span` leaves a cancelled tool span unset (successful-looking) | S17 (OTel); the orphaned tool no longer runs |
| `semantic-kernel-cancelled-function-span.patch` | semantic-kernel `9974625` (1.44.1) | `KernelFunction.invoke` / `invoke_stream` leave a cancelled function's span unset | S17 |
| `google-adk-cancelled-tool-span.patch` | adk-python `51dbf89` (2.11.0) | `record_tool_execution` leaves a cancelled tool's span unset, including siblings cancelled when one parallel call fails | S07, S17 |
| `smolagents-memory-failed-step-tool-calls.patch` | smolagents `c30b115` (1.27.0.dev0) | A step whose tool calls include one failure records no tool calls in memory, so successful calls vanish too | S05, S06, S07 |

Four of the five share one root cause. OpenTelemetry's `use_span` deliberately records only `Exception`, and `asyncio.CancelledError` is a `BaseException`, so a span closed by cancellation keeps an unset status, which back ends display as success. Frameworks that catch only `Exception` around their tool spans inherit this. The fix in each case is to handle `CancelledError` explicitly and mark the span as an error. It is worth saying this once in a short note to the OpenTelemetry Python SIG as well; see `../launch/issues.md`.

## Test results

| Project | Suite run | With the patch | Same as on `main`? |
|---|---|---|---|
| openai-agents-python | full suite (realtime, voice and extensions excluded) | 8,286 passed. 14 failed and 38 errors, all from optional provider extras and docs tooling not installed. | Yes; the only change is the 2 new tests going from fail to pass. |
| autogen | autogen-agentchat suite | 376 passed, 2 failed (`test_declarative_groupchats_with_config`) | Yes, the 2 failures pre-exist |
| autogen | autogen-core suite | 221 passed, 6 failed (protobuf version conflict in the test environment) | Yes, the same 6 fail on `main` |
| semantic-kernel | `tests/unit/functions`, `kernel`, `telemetry` | 187, 102 and 5 passed | Yes; 2 new tests added |
| adk-python | `tests/unittests/telemetry` | 877 passed, 7 xfailed | Yes; 1 new test added |
| smolagents | `test_agents.py`, `test_memory.py`, `test_monitoring.py` | 117 passed, 1 failed (`test_transformers_toolcalling_agent`, which needs a local model) | Yes |

Linting: ruff (OpenAI, AutoGen, Semantic Kernel, smolagents) and pyink with isort (ADK) are clean on the changed lines. Formatting issues that already exist elsewhere in those files were left alone. Not run: each project's full CI wrapper, and type checkers (pyright, mypy). Run those before ticking the checkboxes.

## Before opening each PR

1. Search the project's issue tracker for "cancel" and "span" (or "memory", for smolagents) and link any existing issue instead of filing a duplicate.
2. Fork, clone, branch, then run `git apply <patch>` from the repo root.
3. Run the project's own checks. Each repo's CONTRIBUTING file has the commands; the main ones:
   - openai-agents-python: `make sync`, then `.agents/skills/code-change-verification/scripts/run.sh`
   - autogen: from `python/`, `uv sync --all-extras`, then `poe check`
   - semantic-kernel: from `python/`, `make install`, then `make pre-commit` and `make test`
   - adk-python: `pytest tests/unittests`, plus `pyink` and `isort` per CONTRIBUTING
   - smolagents: `make quality` and `make test`
4. Open the issue first using `../launch/issues.md`, then the PR with the matching description below and "Closes #<issue>".
5. Read each project's contribution rules. Some require a CLA, such as Google's for ADK and Microsoft's for AutoGen and Semantic Kernel. AutoGen is in maintenance mode, so merges there may be slow.

---

## PR: openai-agents-python

**Title:** `fix: record an error on function spans when tool execution is cancelled`

```markdown
### Summary

When a run is cancelled while a function tool is executing, the tool's `FunctionSpanData` span ends with `error=None` and `output=None`. Trace processors and exporters therefore see a successful tool call that never completed.

`SpanImpl.__exit__` ignores the exception type, and the tool executor attaches span errors in an `except Exception` block, which does not see `asyncio.CancelledError` (a `BaseException`). This change attaches a `"Tool execution cancelled"` span error before re-raising. That message is the one already used when a tool-local cancellation is converted by the failure handler. Cancellation still propagates unchanged.

This matches the tool execution lifecycle reference: function spans surround the actual invocation once per call, including failure and cancellation paths.

Relation to #4073 / #4191: those keep `CancelledError` from marking the *agent* span, because a cancelled run is not an agent failure. This change is narrower. It applies only to the *function* span of a tool call that was interrupted before producing output. Today that span is indistinguishable from a successful call that returned `None`, and the SDK already uses `"Tool execution cancelled"` for tool-local cancellation. If you would rather not use `SpanError` for this, an alternative is a non-error marker on `FunctionSpanData` (for example `cancelled=True`). I'm happy to switch to that.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>

### Test plan

- Added `tests/test_tool_cancellation_span_error.py`, covering `Runner.run` (task cancellation) and `Runner.run_streamed` (`result.cancel()`). Both fail on `main` and pass with this change.
- Related tests (`test_tracing_errors*.py`, `test_function_tool.py`, `test_cancel_streaming.py`): 140 passed.
- Full suite: no new failures compared with `main`.
- `ruff check` and `ruff format --check` pass on changed files.

### Issue number

Closes #<issue>

### Checks

- [x] I've added new tests, if relevant
- [ ] I've run `.agents/skills/code-change-verification/scripts/run.sh`
- [ ] I've confirmed all verification steps pass
```

---

## PR: autogen

**Title:** `Fix AssistantAgent hang, orphaned tools and unmarked tool spans when a run is cancelled during tool execution`

```markdown
## Why are these changes needed?

Three cancellation problems around tool execution:

1. **Hang with `CancellationToken`.** If the token is cancelled while a tool runs, `asyncio.gather` raises `CancelledError` inside `_execute_tool_calls` before `stream_queue.put_nowait(None)` runs. The consumer loop (`while True: await stream.get()`) then waits forever, so `agent.run(...)` never returns.
2. **Orphaned tool on task cancellation.** If the task running `agent.run(...)` is cancelled (for example by `asyncio.wait_for`), the tool calls keep running in their own task and their side effects still happen.
3. **Cancelled tool spans look successful.** `trace_tool_span` (autogen-core) handles only `Exception`. `CancelledError` is a `BaseException` that OpenTelemetry also does not record, so the span keeps an unset status.

Changes:
- `AssistantAgent`: queue the end-of-stream sentinel in a `finally` block, and cancel the tool-call task in a `finally` around the consumer loop if the generator exits early.
- `trace_tool_span`: on `CancelledError`, set an ERROR status and `error.type = CancelledError`, then re-raise.

Normal execution is unchanged.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>

## Related issue number

Closes #<issue>

## Checks

- [ ] I've included any doc changes needed for <https://microsoft.github.io/autogen/>. (No doc changes needed.)
- [x] I've added tests (if relevant) corresponding to the changes introduced in this PR.
- [ ] I've made sure all auto checks have passed.

Tests added (all fail on `main` and pass with this change):
- `autogen-agentchat/tests/test_assistant_agent.py::test_cancellation_token_cancelled_during_tool_execution_ends_run`
- `autogen-agentchat/tests/test_assistant_agent.py::test_cancelling_run_task_cancels_in_flight_tool`
- `autogen-core/tests/test_telemetry_tool_span_cancellation.py::test_trace_tool_span_marks_cancelled_tool_as_error`
```

---

## PR: semantic-kernel

**Title:** `Python: Mark function spans as errors when invocation is cancelled`

```markdown
### Motivation and Context

When a kernel function invocation is cancelled (for example a run timed out, or the caller cancelled the task), the `execute_tool` span created in `KernelFunction.invoke` / `invoke_stream` ends with an unset status, so tracing back ends show a successful call that never finished. `CancelledError` is a `BaseException`: it bypasses the existing `except Exception` handler, and OpenTelemetry's `use_span` does not record `BaseException` either.

### Description

Handle `asyncio.CancelledError` alongside the existing handler in both `invoke` and `invoke_stream`: record it on the span with `_handle_exception` (ERROR status plus `error.type`), then re-raise unchanged. `_handle_exception` now accepts `BaseException`.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>

### Contribution Checklist

- [x] The code builds clean without any errors or warnings
- [ ] The PR follows the [SK Contribution Guidelines](https://github.com/microsoft/semantic-kernel/blob/main/CONTRIBUTING.md)
- [x] All unit tests pass, and I have added new tests where possible
- [x] I didn't break anyone :smile:

Added `tests/unit/functions/test_kernel_function_cancellation_tracing.py` (invoke and invoke_stream). Both fail on `main` and pass with this change.
```

---

## PR: adk-python

**Title:** `fix(telemetry): mark execute_tool spans as errors when the tool is cancelled`

```markdown
**Problem**

When a tool call is cancelled, `record_tool_execution` closes its `execute_tool` span with an unset status, so trace back ends show the call as successful. This covers both a cancelled run and a sibling cancelled because another parallel tool call failed. The context manager catches only `Exception`, and `CancelledError` is a `BaseException` that OpenTelemetry's span context manager does not record either.

**Solution**

Catch `asyncio.CancelledError` in `record_tool_execution`, set the scope's `error_type` to `"CancelledError"` (which `trace_tool_call` already turns into an ERROR status, and the duration metric already records), and re-raise. The `error` argument types are unchanged.

Found with TraceGap, a benchmark for tool-call trace completeness (scenarios S07 and S17): <link>

**Testing Plan**

- Added `test_record_tool_execution_marks_cancelled_tool_span_as_error` to `tests/unittests/telemetry/test_instrumentation.py`. It fails on `main` and passes with this change.
- `pytest tests/unittests/telemetry`: 877 passed, 7 xfailed.
- `pyink --check` and `isort --check-only` are clean on changed files.
```

---

## PR: smolagents

**Title:** `Keep tool calls in step memory when a parallel tool call fails`

```markdown
## What does this PR do?

In `ToolCallingAgent.process_tool_calls`, `memory_step.tool_calls` is assigned only after every tool call has returned. If any call raises, the assignment is skipped, so the step's memory records no tool calls at all. Calls that succeeded in the same step disappear from `agent.memory`, and from anything built on it, such as replay and callbacks.

This records the calls in memory before executing them. Observations are still added after execution, as before.

Found with TraceGap, a benchmark for tool-call trace completeness (scenarios S05–S07): <link>

## Tests

Added `test_toolcalling_agent_memory_keeps_tool_calls_when_a_parallel_call_fails` to `tests/test_agents.py`. It fails on `main` and passes with this change. `test_agents.py`, `test_memory.py` and `test_monitoring.py` pass, apart from `test_transformers_toolcalling_agent`, which needs a local model and fails on `main` as well.
```
