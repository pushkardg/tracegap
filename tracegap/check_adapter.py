"""Check a new adapter before opening a pull request.

    python -m tracegap.check_adapter my_package.my_module:MyAdapter [--all] [--repeat 2]

Steps:
  1. Structure: the class subclasses Adapter and sets framework, surface,
     version and capture.
  2. Calibration: scenario S01 (one successful call) must be complete and
     faithful in both modes. If it is not, the adapter is not reading the
     surface correctly yet, and nothing else is meaningful.
  3. No harness errors on the Stable tier of the core suite (an exception in
     the adapter, or a scripted model that never emitted a call).
  4. Determinism: running the Stable tier twice gives identical verdicts.

Exits 0 when all checks pass. Failures that remain after that are findings
about the framework, not adapter bugs; explain each one in the pull request.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
import warnings

from .core import Capture
from .harness import Adapter, run_case
from .scenarios import MODES, SCENARIOS
from .tiers import STABLE, tier


def _load(spec: str):
    mod, _, attr = spec.partition(":")
    if not attr:
        raise SystemExit("expected module:ClassName")
    return getattr(importlib.import_module(mod), attr)()


async def _run(ad, scns):
    out = {}
    for s in scns:
        for m in MODES:
            out[(s.id, m)] = await run_case(ad, s, m)
    return out


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


async def check(spec, include_stress: bool = False, repeat: int = 2) -> bool:
    """spec: "module:ClassName", or an adapter class or factory."""
    ad = _load(spec) if isinstance(spec, str) else spec()
    ok = True

    problems = []
    if not isinstance(ad, Adapter):
        problems.append("does not subclass tracegap.harness.Adapter")
    for attr in ("framework", "surface", "version"):
        if getattr(ad, attr, "?") in ("?", "", None):
            problems.append(f"set the `{attr}` class attribute")
    if not isinstance(getattr(ad, "capture", None), Capture):
        problems.append("set `capture = Capture(args=..., output=..., status=..., call_id=...)`")
    print(f"[{_mark(not problems)}] structure: {ad.key if not problems else spec}")
    for p in problems:
        print(f"       {p}")
    if problems:
        return False

    s01 = [s for s in SCENARIOS if s.id == "S01"]
    cal = await _run(ad, s01)
    cal_ok = all(r.complete and r.faithful for r in cal.values())
    print(f"[{_mark(cal_ok)}] calibration: S01 complete and faithful in invoke and stream mode")
    if not cal_ok:
        for (sid, m), r in cal.items():
            for f in r.failures + r.fidelity_failures:
                print(f"       {sid} {m}: {f}")
        print("       Fix the adapter until S01 passes: it means the surface is not being read correctly.")
        return False

    scns = [s for s in SCENARIOS if include_stress or tier(s) == STABLE]
    runs = [await _run(ad, scns) for _ in range(max(1, repeat))]
    first = runs[0]
    errors = [(k, r.error) for k, r in first.items() if r.run_outcome == "harness-error"]
    print(f"[{_mark(not errors)}] no harness errors on {len(scns)} scenarios x {len(MODES)} modes"
          f" ({'all tiers' if include_stress else 'Stable tier'})")
    for (sid, m), e in errors:
        print(f"       {sid} {m}: {e}")
    ok &= not errors

    if len(runs) > 1:
        diff = [k for k in first if any((r[k].complete, r[k].faithful) != (first[k].complete, first[k].faithful)
                                         for r in runs[1:])]
        print(f"[{_mark(not diff)}] deterministic across {len(runs)} runs")
        for sid, m in diff:
            print(f"       {sid} {m}: verdict changed between runs")
        ok &= not diff

    n = len(first)
    c = sum(r.complete for r in first.values())
    f = sum(r.faithful for r in first.values())
    print(f"\nScore: complete {c}/{n}, faithful {f}/{n}")
    for (sid, m), r in first.items():
        for x in r.failures:
            print(f"  {sid} {m:6s} completeness: {x}")
        for x in r.fidelity_failures:
            print(f"  {sid} {m:6s} fidelity:     {x}")
    if ok:
        print("\nAll checks passed. Remaining failures are findings about the framework: confirm each one by\n"
              "hand and explain it in the pull request (see docs/ADD_YOUR_FRAMEWORK.md).")
    return ok


def main() -> None:
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("adapter", help="module:ClassName, e.g. examples.toy_adapter:ToyHooksAdapter")
    p.add_argument("--all", action="store_true", help="include Stress-tier scenarios")
    p.add_argument("--repeat", type=int, default=2, help="full runs for the determinism check (default 2)")
    a = p.parse_args()
    sys.path.insert(0, ".")
    sys.exit(0 if asyncio.run(check(a.adapter, a.all, a.repeat)) else 1)


if __name__ == "__main__":
    main()
