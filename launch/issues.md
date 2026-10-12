# Upstream issue texts

File the issue first, then the PR from `../upstream-fixes/` with "Closes #<issue>". Search each tracker before filing (try "cancel span", "CancelledError", "memory tool_calls"), and comment on an existing issue instead of duplicating it. Replace `<link>` with the TraceGap repository URL.

Every issue below has a minimal reproduction in `../findings/` or as a regression test in the matching patch.

---

## openai/openai-agents-python

**Title:** Function span reports success when a tool is interrupted by run cancellation

```markdown
**Describe the bug**
If a run is cancelled while a function tool is executing, the tool's `FunctionSpanData` span ends with `error=None` and `output=None`. Trace processors and exporters receive a span that looks like a successful call, although the tool never finished.

**Debug information**
- Agents SDK version: 0.23.1 (also on `main` at 81f0ccf)
- Python version: 3.13

**Repro steps**
Minimal script: <link>/findings/openai_agents_cancelled_tool_reported_ok.py
1. A function tool that sleeps for 2 s.
2. Start `Runner.run(...)` in a task and cancel it after 0.3 s.
3. A custom `TracingProcessor` sees the function span end with `span.error is None`.

**Expected behavior**
The span carries an error (for example "Tool execution cancelled"), as it already does when a tool-local cancellation is converted by the failure handler.

**Cause**
`SpanImpl.__exit__` ignores `exc_type`, and the executor's `except Exception` does not catch `asyncio.CancelledError` (a `BaseException`).

I'm aware of #4073/#4191, which keep cancellation from marking the *agent* span. This issue is only about the *function* span of the interrupted tool call. That span currently looks like a completed call that returned `None`. Whether to record it as a `SpanError` (as tool-local cancellation already is) or with a separate non-error marker is your call. I have a fix with tests for the first option and can adapt it.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>
```

---

## microsoft/autogen

**Title:** AssistantAgent.run() hangs after CancellationToken is cancelled during a tool call; asyncio cancellation leaves the tool running

```markdown
**What happened?**
1. Cancelling a `CancellationToken` while `AssistantAgent` is executing a tool cancels the tool, but `agent.run(...)` never returns. In `_process_model_result`, `_execute_tool_calls` exits with `CancelledError` before `stream_queue.put_nowait(None)` runs, so `while True: await stream.get()` waits forever.
2. Cancelling the asyncio task that runs `agent.run(...)` (for example with `asyncio.wait_for`) does not cancel the tool. It finishes later and its side effects happen after the caller saw the run cancelled.
3. Once the tool is properly cancelled, its `execute_tool` OpenTelemetry span has an unset (successful-looking) status, because `trace_tool_span` handles only `Exception`.

**What did you expect to happen?**
`run()` ends promptly when cancelled by either mechanism, the in-flight tool is cancelled, and its span is marked as an error.

**How can we reproduce it?**
- <link>/findings/autogen_token_cancel_deadlock.py
- <link>/findings/autogen_task_cancel_orphaned_tool.py

**AutoGen version:** 0.7.5 (also on `main` at 027ecf0)
**Which package?** autogen-agentchat, autogen-core
**Python version:** 3.13

I have a fix with tests for all three and can open a PR.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>
```

---

## microsoft/semantic-kernel

**Title:** Python: execute_tool span shows success when a kernel function is cancelled

```markdown
**Describe the bug**
With OTel diagnostics enabled, cancelling a kernel function invocation (for example when the agent run is cancelled while a tool is running) ends its `execute_tool` span with an unset status. Back ends display it as a successful call.

**To Reproduce**
Invoke a `KernelFunctionFromMethod` whose method awaits a long sleep, cancel the task, then inspect the exported span: `status_code == UNSET`.

**Expected behavior**
Status ERROR with `error.type = CancelledError`.

**Cause**
`KernelFunction.invoke` and `invoke_stream` handle `except Exception`. `asyncio.CancelledError` is a `BaseException`, and OpenTelemetry's span context manager does not record it either.

**Platform**
- Language: Python
- Source: semantic-kernel 1.44.1 (also on `main` at 9974625)

I have a fix with tests and can open a PR.

Found with TraceGap, a benchmark for tool-call trace completeness (scenario S17): <link>
```

---

## google/adk-python

**Title:** execute_tool span is not marked as an error when a tool call is cancelled

```markdown
**Describe the bug**
When a tool call is cancelled, its `execute_tool` span ends with an unset status, so trace UIs show it as successful. This covers both a cancelled run and parallel siblings that ADK cancels after one tool raises.

**To Reproduce**
Run an `LlmAgent` with two parallel tool calls where one raises: the sibling is cancelled and its span reads as OK. The same happens when the run is cancelled during a tool.

**Expected behavior**
The span is marked ERROR with `error.type = CancelledError`.

**Cause**
`record_tool_execution` (`telemetry/_instrumentation.py`) catches only `Exception`. `asyncio.CancelledError` is a `BaseException`, which OpenTelemetry's span context manager does not record either.

**Desktop**
- ADK version: 2.11.0 (also on `main` at 51dbf89)
- Python: 3.13

I have a fix with a unit test and can open a PR.

Found with TraceGap, a benchmark for tool-call trace completeness (scenarios S07, S17): <link>
```

---

## huggingface/smolagents (two issues)

**Title 1:** ToolCallingAgent memory drops all tool calls of a step when one parallel call fails

```markdown
**Describe the bug**
In `process_tool_calls`, `memory_step.tool_calls` is assigned only after every tool call returns. If any call raises, the step is recorded with `tool_calls=None`, so calls that succeeded in the same step are missing from `agent.memory` (and from replay and callbacks built on it).

**Code to reproduce the error**
A model that returns two tool calls in one step, one to a tool that raises, then a `final_answer`. After `agent.run(...)`, `agent.memory.steps[1].tool_calls is None`.

**Expected behavior**
The step lists both calls; the error is recorded on the step as today.

**Package versions:** smolagents 1.26.0 (also on `main` at c30b115)

I have a fix with a test and can open a PR.
```

**Title 2:** Tool calls with duplicate ids in one response are silently dropped

```markdown
**Describe the bug**
`process_tool_calls` collects calls in a dict keyed by call id. If a provider returns two different calls with the same id (it happens with some providers and proxies), the first call is silently overwritten. It is neither executed nor recorded, and no warning is logged.

**Expected behavior**
Either execute both calls, or reject the response with an error the agent can see. A silent drop is the one outcome a trace cannot reveal.

**Package versions:** smolagents 1.26.0

Found with TraceGap (scenario S11): <link>
```

---

## OpenTelemetry Python (optional discussion post)

Post to the OpenTelemetry GenAI semantic conventions SIG (Slack `#otel-genai-instrumentation`) or as a discussion on `open-telemetry/opentelemetry-python`. Don't file it as a bug; `use_span`'s behaviour is deliberate.

```markdown
**Cancelled tool calls show as successful across GenAI instrumentations**

`use_span` deliberately records only `Exception`, so a span closed by `asyncio.CancelledError` keeps status UNSET. In GenAI instrumentation this means a tool call interrupted by cancellation (a timeout, a user abort, or a sibling cancelled after a parallel failure) is displayed as successful.

TraceGap (<link>) measured this in several agent frameworks; Semantic Kernel, Google ADK and AutoGen (after its orphaned-tool fix) were affected, and Pydantic AI handles it explicitly. Fixes are being proposed to each framework.

Would it make sense for the GenAI semantic conventions to state how cancellation should be recorded on `execute_tool` spans (for example status ERROR with `error.type = "CancelledError"`, or a dedicated value), so instrumentations behave consistently?
```
