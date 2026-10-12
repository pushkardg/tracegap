# Your agent's trace is lying to you (a little): measuring tool-call trace completeness in nine agent frameworks

*Draft for your blog, Medium, dev.to or a company engineering blog. About 1,300 words. Replace `<link>` with the repo URL and check the numbers against `results/LEADERBOARD.md` before posting.*

---

When an LLM agent misbehaves in production, the first thing anyone opens is the trace. Which tools did it call, with what arguments, and what came back? Observability dashboards, audit logs, evaluation pipelines and incident reviews all start from that record.

We tend to treat the trace as ground truth. But it isn't produced by the model, and usually not by your application either. It's produced by the agent framework: callbacks in LangGraph, tracing spans in the OpenAI Agents SDK, OpenTelemetry spans in Pydantic AI, Semantic Kernel and Google ADK, events in CrewAI and LlamaIndex. If the framework drops a call, or reports a cancelled call as successful, everything downstream inherits the error and nobody notices.

So I measured it.

## How TraceGap works

TraceGap drives each framework with a **scripted model**, so every framework faces exactly the same sequence of tool calls. No API keys, no network, and deterministic results. It then compares the framework's own trace against two pieces of ground truth that don't depend on the framework at all:

- **the emission log:** every tool call the scripted model asked for, and
- **the execution ledger:** every tool call that actually started, with its real arguments and real outcome, written from inside the tool.

Each tool call carries a unique tag, so recorded events are matched to ground truth without trusting framework-assigned ids. A case is **complete** if every call is present with an honest status, with no phantom or duplicate calls and no runs mixed together or split apart. It is **faithful** if every argument, output and error message the surface claims to capture is exact.

The 22 core scenarios are the situations production agents actually hit:
- parallel calls;
- failing tools;
- calls to tools that don't exist;
- invalid arguments;
- duplicate call ids from a provider;
- a 200,000-character output;
- cancellation mid-tool;
- a provider error after tools ran;
- turn limits;
- concurrent runs;
- an agent used as a tool.

Each runs in invoke and stream mode. A seeded generator adds hundreds more random but reproducible scenarios.

## Results

Nine frameworks, fifteen trace surfaces, 660 core cases. **586 (88.8%) were complete, and 566 (85.8%) were both complete and faithful.** One surface, CrewAI's event bus, was perfect. The other fourteen missed something. The full matrix is at `<link>`.

That's mostly good news: ordinary successful calls are recorded correctly everywhere. The gaps cluster in exactly the places where you most need the trace.

### 1. Cancelled tool calls show up as successful

This was the most surprising finding (the most common gap is rejected calls that leave no trace; see below). When a run is cancelled while a tool is executing (a timeout, a user abort, a sibling cancelled because another parallel call failed), several frameworks closed the tool's span with **no error status**. In a tracing UI, the call looks like it succeeded.

The cause is shared. OpenTelemetry's `use_span` deliberately records only `Exception`, and `asyncio.CancelledError` is a `BaseException`. Any framework that wraps tool execution in `except Exception` inherits the problem. I found it in the OpenAI Agents SDK, Semantic Kernel, Google ADK and AutoGen. Pydantic AI handles it correctly.

### 2. Failed runs can take their history with them

AutoGen's `TaskResult.messages` only exists if the run completes. If the run is cancelled or the model provider fails, the calls that *had already succeeded* are gone. The same calls survive if you consume `run_stream()` instead. smolagents had a related bug: if one call in a parallel step failed, the step's memory recorded *no* calls, including the ones that worked.

### 3. Rejected calls leave no trace

When a model calls a tool that doesn't exist, most tool-level surfaces record nothing. The attempt survives only in the raw model output. For debugging hallucinated tool names, that's the wrong place to have to look.

### 4. Nested agents vanish from per-agent histories

Calls made by an agent used as a tool are missing from the outer agent's message history in some frameworks, but present in their tracing and OpenTelemetry surfaces.

### 5. Error details are often withheld

The OpenAI Agents SDK withholds tool error messages from spans when the default error handler is used. Running TraceGap across its releases shows this arriving in 0.23. It's deliberate and privacy-motivated, but you should know about it if you debug from traces.

## It found real bugs, and they're fixable

TraceGap found defects in five frameworks. For each, I wrote a minimal fix with a regression test that fails before the fix and passes after, and confirmed that TraceGap's own scenarios pass with the patched framework:

- **OpenAI Agents SDK:** cancelled function spans now carry an error.
- **AutoGen:** `run()` no longer hangs when cancelled through its token; cancelling the run now cancels the in-flight tool; and the tool span is marked as an error.
- **Semantic Kernel:** cancelled function invocations are marked as errors.
- **Google ADK:** cancelled tool spans, including cancelled parallel siblings, are marked as errors.
- **smolagents:** a step's memory keeps its tool calls when one of them fails.

*(Update with PR links and status once opened.)*

## It's also a history

Because the models are scripted, I could run the same suite against **65 past releases** of the nine frameworks. Each release's dependencies were resolved as of its release date, so each run sees what users actually installed at the time. That shows when gaps appeared and disappeared:
- smolagents' memory bug arrived together with parallel tool calls in 1.18;
- Pydantic AI's OpenTelemetry spans started showing rejected calls in 2.30;
- the OpenAI SDK's error redaction arrived in 0.23.

## Is the benchmark itself right?

Two checks, because a benchmark that can't fail is worthless:

- **A reference loop.** About 100 lines of deliberately correct bookkeeping. It scores complete and faithful on every core case and every generated case, so a perfect score is achievable.
- **Mutation testing.** I injected eleven different recording bugs into that loop, one at a time: dropping rejected calls, reporting cancellations as success, merging runs, truncating outputs, and others. Each was caught by the scenario designed for it.

## Use it

```bash
pip install tracegap
python -m tracegap.cli -v
```

- **Framework maintainers:** there's a GitHub Action and a pytest helper that turns each scenario into a test, with known gaps as strict xfails. CI then tells you when you fix one, and fails if you regress one.
- **Observability vendors:** the OpenTelemetry and OpenInference collectors mean any instrumented framework can be measured with only the code that drives it.
- **Researchers:** the labeled corpus (ground truth next to the recorded trace, for every case) is on Hugging Face.

Code, data, results and fixes: `<link>`. If your framework isn't covered, adapters are around 100 lines, and I'd welcome a PR.
