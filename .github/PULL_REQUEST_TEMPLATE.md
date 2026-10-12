## What this changes

<!-- New framework adapter, new scenario, scorer change, docs, other. -->

## New or changed adapter

- Framework and surface (`<framework>/<surface>`):
- Framework version tested:
- `capture` (what the surface records): args / output / status / call_id

Output of `python -m tracegap.check_adapter <module>:<Class>` (all four checks must pass):

```
paste here
```

Remaining failures, one line each with the cause you confirmed by hand:

| Scenario | Mode | Failure | Cause |
|---|---|---|---|
|  |  |  |  |

## Checklist

- [ ] The adapter reads events only through the framework's public observability surface (no rebuilding from the ledger, no patching internals).
- [ ] The scripted model answers tool-less final calls in text without consuming the script.
- [ ] Factory registered in `tracegap/adapters/__init__.py`; `envs/<framework>.txt` added if dependencies conflict.
- [ ] `pytest` passes.
- [ ] Scenario or scorer changes: verdicts stable across three full runs; scorer changes have a negative control in `tests/test_scorer.py` and, for a new kind of check, an injected defect in `tracegap/adapters/reference.py`.
