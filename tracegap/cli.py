"""Command-line entry point: ``python -m tracegap.cli [options]``."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import warnings
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .harness import run_case
from .scenarios import MODES, SCENARIOS


def load_external(specs: list[str]):
    """Load adapters given as ``package.module:ClassOrFactory``."""
    import importlib

    out = []
    for spec in specs or []:
        mod, _, attr = spec.partition(":")
        obj = getattr(importlib.import_module(mod), attr)
        out.append(obj())
    return out


def load_adapters(names: list[str] | None):
    from .adapters import ADAPTERS

    out = []
    for key, factory in ADAPTERS.items():
        if names and key not in names and key.split("/")[0] not in names:
            continue
        try:
            out.append(factory())
        except ImportError as e:
            print(f"skipping {key}: {e}", file=sys.stderr)
    return out


async def main_async(args) -> int:
    adapters = load_external(args.adapter_module)
    if not args.adapter_module or args.adapters:
        adapters += load_adapters(args.adapters)
    if args.suite == "generated":
        from .generator import generate

        pool = generate(args.n, args.seed)
        suite_name = f"generated(n={args.n}, seed={args.seed})"
    else:
        pool = SCENARIOS
        suite_name = "core"
    scns = [s for s in pool if not args.scenarios or s.id in args.scenarios]
    if args.tier != "all":
        from .tiers import tier

        scns = [s for s in scns if tier(s) == args.tier]
    modes = args.modes or MODES
    results = []
    for ad in adapters:
        for s in scns:
            for m in modes:
                r = await run_case(ad, s, m)
                results.append(r)
                c = "C" if r.complete else "-"
                f = "F" if r.faithful else "-"
                print(f"[{c}{f}]  {ad.key:28s} {s.id} {m:6s} [{r.run_outcome}]")
                if args.verbose:
                    for x in r.failures:
                        print(f"        completeness: {x}")
                    for x in r.fidelity_failures:
                        print(f"        fidelity:     {x}")
    out = {
        "benchmark": "TraceGap",
        "suite": suite_name,
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "adapters": {a.key: {"version": a.version, "capture": asdict(a.capture)} for a in adapters},
        "scenarios": {s.id: {"category": s.category, "title": s.title, "description": s.description} for s in scns},
        "results": [{k: v for k, v in asdict(r).items() if k != "trace"} for r in results],
    }
    if args.traces:
        tdir = Path(args.traces)
        tdir.mkdir(parents=True, exist_ok=True)
        for ad in adapters:
            fn = tdir / (ad.key.replace("/", "__") + ".jsonl")
            with fn.open("w") as fh:
                for r in results:
                    if r.adapter != ad.key:
                        continue
                    row = {"adapter": r.adapter, "scenario": r.scenario, "mode": r.mode,
                           "complete": r.complete, "faithful": r.faithful, "run_outcome": r.run_outcome,
                           "failures": r.failures, "fidelity_failures": r.fidelity_failures, **(r.trace or {})}
                    fh.write(json.dumps(row, default=str) + "\n")
        print(f"wrote trace corpus to {tdir}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=str))
        print(f"wrote {args.out}")
    status = 0
    if args.baseline:
        from .compare import compare, render_comparison

        base = json.loads(Path(args.baseline).read_text())
        diff = compare(base, out)
        print(render_comparison(diff))
        if diff["regressions"]:
            status = 1
    if args.fail_on != "none":
        key = "complete" if args.fail_on == "incomplete" else "passed"
        bad = [r for r in results if not getattr(r, key)]
        if bad:
            print(f"{len(bad)} case(s) not {key}; failing as requested by --fail-on {args.fail_on}")
            status = 1
    return status


def main() -> None:
    import os

    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser(prog="tracegap")
    p.add_argument("--adapters", nargs="*", help="adapter keys or framework names (default: all)")
    p.add_argument("--scenarios", nargs="*", help="scenario ids, e.g. S01 S17 (default: all)")
    p.add_argument("--modes", nargs="*", choices=MODES)
    p.add_argument("--suite", choices=["core", "generated"], default="core",
                   help="core: the 22 hand-written scenarios; generated: seeded random scenarios")
    p.add_argument("--tier", choices=["all", "stable", "stress"], default="all",
                   help="stable: scenarios with deterministic verdicts (use for CI); stress: race-sensitive ones")
    p.add_argument("--n", type=int, default=200, help="generated suite size")
    p.add_argument("--seed", type=int, default=1, help="generated suite seed")
    p.add_argument("--out", default="tracegap-results/results.json")
    p.add_argument("--traces", default="tracegap-results/traces", help="directory for the labeled trace corpus ('' to skip)")
    p.add_argument("--adapter-module", nargs="*", default=[],
                   help="external adapters as module:Class (e.g. myproj.tracegap_adapter:MyAdapter)")
    p.add_argument("--baseline", help="earlier results.json; exit 1 if any case regressed")
    p.add_argument("--fail-on", choices=["none", "incomplete", "any"], default="none",
                   help="exit 1 if any case is incomplete (or, with 'any', incomplete or unfaithful)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
