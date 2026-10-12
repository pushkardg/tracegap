"""Detection rate of each injected defect on the generated suite (n=200, seed=1)."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracegap.adapters.reference import DEFECTS, ReferenceAdapter
from tracegap.generator import generate
from tracegap.harness import run_case
from tracegap.scenarios import MODES

async def main():
    scns = generate(200, 1)
    out = {}
    for d in [None] + list(DEFECTS):
        ad = ReferenceAdapter({d} if d else set())
        rows = []
        for s in scns:
            for m in MODES:
                r = await run_case(ad, s, m)
                rows.append([s.id, m, r.complete, r.faithful, r.run_outcome == "harness-error"])
        out[d or "none"] = rows
        print(d, sum(1 for x in rows if not (x[2] and x[3])), flush=True)
    out_dir = Path(__file__).resolve().parents[1] / "analysis" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mutation_generated.json").write_text(json.dumps(out))

asyncio.run(main())
