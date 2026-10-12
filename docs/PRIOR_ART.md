# Prior-art search

TraceGap's novelty claim is that no prior benchmark measures whether agent frameworks record the tool calls their agents make, completely and accurately, against ground truth that does not depend on the framework. This file records the search behind that claim so that others can repeat or extend it.

## Method

- **Date:** 3 October 2026.
- **Sources:** general web search (which indexes arXiv, ACL Anthology, OpenReview, publisher sites, Hugging Face and GitHub), followed by reading the abstract and, for close matches, the method section of each candidate.
- **Queries:**
  1. agent observability benchmark
  2. LLM tracing benchmark
  3. OpenTelemetry LLM benchmark
  4. agent provenance benchmark
  5. tool call tracing evaluation
  6. LLM trace completeness
  7. agent execution provenance dataset
  8. benchmark whether agent frameworks record tool calls correctly in traces
  9. OpenTelemetry instrumentation correctness testing
  10. empirical study of observability bugs in LLM agent frameworks
  11. Hugging Face datasets of agent traces with tool calls
  12. comparisons of LLM observability tools against ground truth
- **Inclusion:** any work that (a) evaluates or benchmarks traces, logs, spans or provenance records of LLM agents, or (b) releases a dataset of such records with labels.
- **Question asked of each:** does it compare what a framework *recorded* with what *actually executed*, using ground truth independent of the framework?

## Closest work

| Work | What it does | Does it measure recording correctness against independent ground truth? |
|---|---|---|
| Wang et al., *From Agent Traces to Trust* (survey, arXiv:2606.04990, 2026) | Surveys evidence tracing and execution provenance in LLM agents. | No. Describes the area as fragmented and lists unified trace schemas as an open challenge; proposes no measurement of recording correctness. |
| Zhu et al., *Bugs in Modern LLM Agent Frameworks: An Empirical Study* (arXiv:2602.21806, 2026) | Classifies 998 bug reports from CrewAI and LangChain. | No, but complementary: 32 of the 998 bugs (3.2%) have the root cause "Telemetry Malfunction", defined as tracing, logging or observability components that interfere with execution or fail to capture state transitions. This is independent evidence that recording defects occur in practice; it does not measure them systematically. |
| Deshpande et al., *TRAIL* (arXiv:2505.08638, 2025) | 148 OpenInference traces annotated with agent errors (reasoning, execution, planning). | No. Labels errors *of the agent* inside traces and takes the traces themselves as correct. |
| Hmimou et al., *AgentSec* dataset (Data 11(4):66, 2026) | 30 synthetic scenarios with decision traces, tool calls and W3C PROV graphs, used to audit reasoning consistency. | No. The traces are generated from scenario specifications, not recorded by agent frameworks, so recording defects cannot arise. |
| Seyedghorban et al., *Observability and Fault Injection for LLM-Based Multi-Agent Systems* (arXiv:2608.24271, 2026) | OpenTelemetry instrumentation plus fault injection (delays) in multi-agent workflows, measuring runtime amplification. | No. Uses observability to study the effect of injected faults on the agent; does not test whether the recorded trace is correct. |
| AlSayyad et al., *AgentTrace* (arXiv:2602.10133, 2026) | A structured logging framework for agent observability. | No. Proposes a new tracing layer; does not evaluate existing frameworks' traces. |
| Qin et al., *LLM Agents Can Easily Tamper With Their Own Traces* (arXiv:2609.30266, 2026) | Shows agents can delete or alter their own traces when incentivized. | No, and complementary: adversarial tampering by the agent, not honest recording errors by the framework. Both argue for records that do not depend on the component being audited. |
| Dutta and Moharir, *Trace Integrity for LLM Data Agents* (arXiv:2608.26036, 2026) | Vision paper defining trace integrity for data agents; proof-of-concept on SQL traces. | No. "Trace" here means the agent's generated computation (SQL), checked against gold queries, not a framework's execution record. |
| Agent-Sentry (Sequeira et al., arXiv:2603.22868, 2026) | Uses execution provenance to block prompt-injection attacks. | No. Consumes provenance; does not evaluate its correctness. |
| Tool-use benchmarks: Gorilla, ToolLLM, τ-bench, AgentBench | Evaluate the model's tool selection, arguments and task success. | No. They evaluate models, not frameworks' records. |
| OpenTelemetry GenAI semantic conventions; OpenInference | Define span formats for agents and tool calls. | No. Specifications, with no conformance or correctness suite for agent frameworks. |
| Vendor comparisons of observability platforms (Langfuse, LangSmith, Phoenix, and others) | Feature and pricing comparisons. | No ground-truth evaluation of recording correctness found. |
| Practitioner posts on contract and mutation testing of OpenTelemetry spans | Advise testing that instrumentation emits expected spans in one's own service. | No benchmark; general advice, not specific to agent frameworks. |

## Conclusion

The search found work that **consumes** agent traces (failure attribution, provenance, security), work that **labels agent errors inside** traces assumed correct, a **synthetic** provenance dataset, and an empirical bug study showing that telemetry malfunctions are a real bug class. It found no benchmark or dataset that compares what agent frameworks record about tool calls with what actually executed, using ground truth independent of the framework.

The paper therefore states the claim as "to our knowledge, no prior benchmark", cites the closest work above, and points to this file. A search can miss work, especially unindexed industry tooling; corrections are welcome as issues.

## References

- Y. Wang, J. Zhang, T. Cai, Z. Liu, Q. Sun, Z. Sun, Z. Wu, M. Zhang, Y. Zhu. From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in LLM Agents. arXiv:2606.04990, 2026.
- X. Zhu, J. Wu, X. Zhang, T. Li, Y. Mu, J. Zhai, C. Shen, C. Fang, Y. Liu. Bugs in Modern LLM Agent Frameworks: An Empirical Study. arXiv:2602.21806, 2026.
- D. Deshpande, V. Gangal, H. Mehta, J. Krishnan, A. Kannappan, R. Qian. TRAIL: Trace Reasoning and Agentic Issue Localization. arXiv:2505.08638, 2025.
- Y. Hmimou, M. Tabaa, A. Khiat, Z. Hidila. A Dataset Capturing Decision Processes, Tool Interactions and Provenance Links in Autonomous AI Agents. Data 11(4):66, 2026. doi:10.3390/data11040066.
- Z. Seyedghorban, E. Klimov, A. van Deursen, A. Panichella, B. Kulahcioglu Ozkan. Observability and Fault Injection for LLM-Based Multi-Agent Systems in Software Engineering. arXiv:2608.24271, 2026.
- A. AlSayyad, K. Y. Huang, R. Pal. AgentTrace: A Structured Logging Framework for Agent System Observability. arXiv:2602.10133, 2026.
- J. Qin, D. Schmotz, D. Prinzhorn, L. Beurer-Kellner, A. Prabhu, M. Andriushchenko. LLM Agents Can Easily Tamper With Their Own Traces. arXiv:2609.30266, 2026.
- S. Dutta, A. K. Moharir. Trace Integrity for LLM Data Agents: A Vision for Auditable Structured Reasoning in Real-World Systems. arXiv:2608.26036, 2026.
- R. Sequeira, S. Damianakis, U. Iqbal, K. Psounis. Agent-Sentry: Bounding LLM Agents via Execution Provenance. arXiv:2603.22868, 2026.
