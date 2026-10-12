# Add your framework to TraceGap

If you maintain an agent framework, an observability integration, or just use one, you can add it to TraceGap in an afternoon. A typical adapter is 100 to 200 lines. Once it is merged, your framework appears on the leaderboard, its traces join the dataset, and you can run it in your own CI to learn when a release changes what gets recorded (see the end of this guide).

## 1. Start from the example

[`examples/toy_adapter.py`](../examples/toy_adapter.py) is a complete adapter for a tiny made-up framework, in one file. Copy it to `tracegap/adapters/<framework>_adapters.py` and replace the toy framework with yours.

An adapter does three things:

| Method | What it does |
|---|---|
| `setup_case(scenario, mode)` | Reset whatever collects trace events (a callback handler, an in-memory span exporter, an event listener). |
| `run(run_index, script, scenario, mode)` | Build an agent with a **scripted model** and the scenario's tools, then run it in `invoke` or `stream` mode. |
| `collect()` | Return what the framework recorded, as a list of `TraceEvent`, read **only** through its public observability surface. |

And sets four attributes: `framework`, `surface` (for example `callbacks`, `otel`, `events`), `version`, and `capture`, which says honestly what the surface records. Fields set to `False` in `capture` are not scored, so a surface that never records outputs is not penalized for missing them.

### The scripted model

Wrap `ScriptCursor` in your framework's model interface. Each call to `await cursor.next_turn()` returns the next `Turn`: either tool calls (`turn.calls`, each with `call_id`, `name`, `args`) or a final answer (`turn.final`). The cursor also logs every emitted call as ground truth, so always go through it.

If your framework asks the model for a tool-less final answer (for example after a turn limit), answer in text **without** calling `next_turn()`, so the script is not consumed. The Semantic Kernel, smolagents and CrewAI adapters show how.

### The tools

Use `tracegap.tools.TOOLS[name]` for every name in `scenario.tools`. The tools write the execution ledger themselves; that ledger is the ground truth. For `delegate` (scenario S22, a nested agent), use `make_delegate(run_inner)` where `run_inner` runs a second agent built from `script.nested` with `ScriptCursor(script.nested, run_index, nested=True)`.

Map `scenario.max_model_calls` to your framework's turn or iteration limit.

### Reading the trace

Convert each recorded tool call to a `TraceEvent`:

```python
TraceEvent(
    name="echo",                  # tool name as recorded
    args={"tag": "t1", ...},      # parsed arguments, or None if not recorded
    status="ok",                  # ok | error | incomplete | unknown
    output="echo:hello",          # or None
    error=None,                   # error message, if recorded
    call_id="call_r0_t1",         # the model's tool-call id, if recorded
    group="<trace or run id>",    # what the surface says the call belongs to
    order=1,
)
```

`group` must come from the surface (a trace id, a root run id, a session id). TraceGap uses it to check that concurrent runs are not mixed and that one run is not split into pieces. For OpenTelemetry GenAI or OpenInference spans, reuse `tracegap.collectors` instead of parsing spans yourself.

**Do not** rebuild events from the ledger, patch framework internals, or repair what the surface records. The benchmark scores the surface as a consumer sees it. Decoding a format any consumer would decode (for example JSON-wrapped tool outputs) is fine; say so in the adapter's docstring.

## 2. Check it

```bash
python -m tracegap.check_adapter tracegap.adapters.myframework_adapters:MyFrameworkCallbacks
```

The checker verifies the class structure, then runs the calibration scenario S01 (one successful call) in both modes. If S01 is not complete and faithful, the adapter is not reading the surface correctly yet and nothing else is meaningful. It then runs the Stable tier of the core suite twice and confirms there are no harness errors and the verdicts are identical. Add `--all` to include the Stress tier.

Running it on the toy example shows what findings look like:

```
[PASS] structure: toy/hooks
[PASS] calibration: S01 complete and faithful in invoke and stream mode
[PASS] no harness errors on 21 scenarios x 2 modes (Stable tier)
[PASS] deterministic across 2 runs

Score: complete 36/42, faithful 40/42
  S11 invoke completeness: t1: executed (ok) but missing from trace
  S16 invoke completeness: t1: actual=ok but trace status=error
  S22 invoke completeness: run 0: its calls are split across 2 unrelated trace groups
  ...
```

These are real defects in the toy framework, which is the point: it keys records by call id, so a repeated id overwrites the first record (S11); it awaits synchronous tools, so they fail (S16); and a nested agent starts a new run id (S22). For each failure that remains in your framework, confirm the cause by hand and write one line explaining it in the pull request. If a failure turns out to be an adapter mistake, fix the adapter.

## 3. Register and open the pull request

1. Add a factory to `ADAPTERS` in [`tracegap/adapters/__init__.py`](../tracegap/adapters/__init__.py), keyed `<framework>/<surface>`.
2. If the framework's dependencies conflict with the others, add `envs/<framework>.txt` with pinned versions and an entry in `scripts/run_all.sh`. Add an optional dependency group to `pyproject.toml`.
3. Optionally add regression tests with the pytest helper:

   ```python
   # tests/test_myframework.py
   import pytest
   from tracegap.testing import cases, check
   from tracegap.adapters.myframework_adapters import MyFrameworkCallbacks

   # Stable tier by default; known gaps are strict xfails.
   @pytest.mark.parametrize("case", cases(MyFrameworkCallbacks, known_gaps={"S11"}))
   def test_trace(case):
       check(case)
   ```

4. Open the pull request using the template. It asks for the checker output and one line per remaining failure.

A framework with several surfaces (for example callbacks and OpenTelemetry) gets one adapter per surface; they are ranked separately.

## Adding the benchmark to your own CI instead

If you maintain a framework and want regression checks without adding it here, use the GitHub Action with your adapter module:

```yaml
- uses: pushkardg/tracegap@v1
  with:
    adapter-module: my_package.tracegap_adapter:MyAdapter
    tier: stable
    fail-on: incomplete
```

See the README's CI section for baselines and pytest usage.
