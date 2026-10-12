"""Run the reference loop with each injected defect over the core suite and
record which cases detect it, and on which axis."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracegap.adapters.reference import DEFECTS, ReferenceAdapter
from tracegap.harness import run_case
from tracegap.scenarios import MODES, SCENARIOS

async def main():
    out = {}
    for d in [None] + list(DEFECTS):
        ad = ReferenceAdapter({d} if d else set())
        rows = []
        for s in SCENARIOS:
            for m in MODES:
                r = await run_case(ad, s, m)
                rows.append({"scenario": s.id, "mode": m, "complete": r.complete, "faithful": r.faithful,
                             "harness_error": r.run_outcome == "harness-error"})
        out[d or "none"] = rows
        bad = [x for x in rows if not (x["complete"] and x["faithful"])]
        print(d, len(bad), sorted({x["scenario"] for x in bad}), flush=True)
    out_dir = Path(__file__).resolve().parents[1] / "analysis" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mutation_matrix.json").write_text(json.dumps(out, indent=1))

asyncio.run(main())
