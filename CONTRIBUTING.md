# Contributing

The most useful contributions are new framework adapters and new scenarios.

## Adding a framework adapter

The step-by-step guide, with a one-file example adapter, is [docs/ADD_YOUR_FRAMEWORK.md](docs/ADD_YOUR_FRAMEWORK.md). In short:

1. Create `tracegap/adapters/<framework>_adapters.py` (one file per framework, one class per surface) with a class that subclasses `tracegap.harness.Adapter` and sets:
   - `framework`, `surface`, `version`
   - `capture = Capture(args=..., output=..., status=..., call_id=...)`. Say honestly what the surface records; fields marked `False` are not scored.
2. Implement:
   - `setup_case(scenario, mode)`: reset whatever collects trace events.
   - `run(run_index, script, scenario, mode)`: build an agent with the scenario's tools (from `tracegap.tools.TOOLS`, plus `make_delegate` for S22) and a scripted model that wraps `ScriptCursor(script, run_index)`, then run it in `invoke` or `stream` mode. Map `scenario.max_model_calls` to the framework's turn limit.
   - `collect()`: return the recorded tool calls as `TraceEvent`s. Read them **only** through the framework's public observability surface. Do not rebuild events from the ledger or patch framework internals.
3. Register the factory in `tracegap/adapters/__init__.py`.
4. Run `python -m tracegap.check_adapter <module>:<Class>`. All four checks (structure, calibration, no harness errors, determinism) must pass. Then check the remaining failures by hand: every failure in a pull request should come with a short explanation of its cause.

If a framework offers several surfaces (for example callbacks and OpenTelemetry), add one adapter per surface. For surfaces that emit OpenTelemetry GenAI or OpenInference spans, reuse `tracegap.collectors` instead of parsing spans yourself.

Rules that keep comparisons fair:
- If the framework asks the model for a tool-less final answer (after a turn limit, for example), the scripted model must answer in text without consuming the script; see the Semantic Kernel, smolagents and CrewAI adapters.
- Do not repair or reinterpret what the surface records, beyond decoding a format any consumer would decode (for example LlamaIndex's JSON-wrapped `ToolOutput` in OpenInference spans). Document any such decoding in the adapter's docstring.
- If the framework has conflicting dependencies, add `envs/<framework>.txt` and an entry in `scripts/run_all.sh`.
- To support older releases, prefer small import or signature shims (see the OpenAI Agents and LlamaIndex adapters). Add the framework's versions to `scripts/run_versions.py`.

## Adding a scenario

Add it to `tracegap/scenarios.py`. A good scenario:
- reflects something that happens in production (provider glitch, timeout, partial failure);
- gives every call a unique `tag`;
- does not depend on timing tighter than about 100 ms.

Run the full suite three times and confirm the verdicts are stable before opening a pull request. If the scenario's outcome can legitimately depend on scheduling, make sure `tracegap/tiers.py` places it in the Stress tier. New primitives for the generator go in `tracegap/generator.py`; never change what an existing `(n, seed)` produces without bumping the benchmark version, because published results cite it.

## Scorer changes

Any change to `tracegap/harness.py:score` needs a matching negative control in `tests/test_scorer.py`, and, if it introduces a new kind of check, an injected defect in `tracegap/adapters/reference.py` that only that check catches (see `tests/test_integration.py`).
