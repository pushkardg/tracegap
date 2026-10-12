# Social posts

Check the numbers against `results/LEADERBOARD.md` before posting. Post the LinkedIn and X versions the day the repo, dataset and arXiv paper are live; post Show HN on a weekday morning (US Pacific).

---

## LinkedIn

> When an AI agent misbehaves in production, the first thing we open is the trace. But how often does the trace match what the agent actually did?
>
> I built TraceGap to measure that. It drives agent frameworks with scripted models (no API keys, deterministic) through 22 fault scenarios, then compares each framework's own trace (callbacks, OpenTelemetry spans, events, message history) against ground truth written by the tools themselves.
>
> Across 9 frameworks and 15 trace surfaces:
> • on the deterministic (Stable) cases, 74.6% were complete; on the hand-written core suite, 88.8%; 1 surface was perfect
> • the most common gap: tool calls the framework rejects (unknown tool, bad arguments) leave no tool-level trace
> • the most surprising: tool calls interrupted by cancellation are often reported as *successful*, because OpenTelemetry's span helper does not record cancellation
> • failed runs can lose calls that had already succeeded; rejected tool calls often leave no trace at all
>
> TraceGap found defects in 5 frameworks (OpenAI Agents SDK, AutoGen, Semantic Kernel, Google ADK, smolagents). I've written fixes with regression tests for each.
>
> It's open source, with a labeled dataset of about 11,500 traces, including 65 past framework releases, a GitHub Action, and a pytest helper for framework maintainers.
>
> Code, results and dataset: <link>
>
> #AIagents #observability #OpenTelemetry #LLMOps

---

## X / Bluesky thread

1/ Your agent's trace is the record you debug from, audit and evaluate. Does it match what the agent actually did?

I built TraceGap to check: 9 agent frameworks, 15 trace surfaces, scripted models, ground truth written by the tools themselves. 🧵 <link>

2/ Mostly yes: 88.8% of 660 cases complete. But the gaps sit exactly where you need the trace most: cancellation, failures, rejected calls, nested agents.

3/ Most surprising: a tool call interrupted by cancellation often shows up as *successful*. OTel's use_span only records Exception, and CancelledError is a BaseException. Seen in 3 frameworks, and a 4th once another bug is fixed.

4/ Others:
- a failed run can lose calls that already succeeded
- a call to a nonexistent tool often leaves no tool-level trace
- calls by an agent-as-tool vanish from per-agent history

5/ TraceGap found defects in 5 frameworks. Fixes with regression tests for all of them: OpenAI Agents SDK, AutoGen, Semantic Kernel, Google ADK, smolagents.

6/ Since the models are scripted, I could also run 65 past releases. You can see bugs arrive (smolagents memory loss came with parallel tool calls in 1.18) and get fixed.

7/ Use it: `pip install tracegap`. There's a GitHub Action and pytest helper for maintainers, OTel/OpenInference collectors for vendors, and a labeled HF dataset for researchers. <link>

---

## Show HN

**Title:** Show HN: TraceGap – does your AI agent framework's trace match what actually ran?

**Text:**

> TraceGap is a small benchmark that checks whether agent frameworks record tool calls correctly. It drives each framework with a scripted model (no API keys, runs in minutes) through scenarios like cancellation mid-tool, failing parallel calls, calls to nonexistent tools, duplicate provider call ids and nested agents. It then compares the framework's own trace against a ledger written by the tools themselves.
>
> Across 9 Python frameworks (LangGraph, OpenAI Agents SDK, Pydantic AI, AutoGen, smolagents, LlamaIndex, Semantic Kernel, Google ADK, CrewAI) and 15 surfaces (callbacks, OTel, OpenInference, events, history), 88.8% of the hand-written cases are complete (74.6% of the deterministic cases across both suites). The most common gap is rejected calls that leave no tool-level trace; the most surprising is cancelled tool calls showing up as successful, because OpenTelemetry's use_span doesn't record BaseException and CancelledError is one. I've written fixes for the five frameworks where it found defects.
>
> Repo, leaderboard and dataset: <link>. Happy to add frameworks; an adapter is 100 to 200 lines.

---

## Reddit (r/LocalLLaMA, r/MachineLearning [P])

**Title:** [P] TraceGap: measuring whether agent frameworks' traces match what actually ran (9 frameworks, 15 surfaces, open dataset)

Use the Show HN text. In r/MachineLearning, lead with the method (scripted models, framework-independent ledger, mutation-tested scorer) and the dataset.
