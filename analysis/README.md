# Paper analyses

Everything in the TMLR paper (`paper/tmlr/`) is produced from the released results by the scripts here.
Run from the repository root, in an environment with the analysis dependencies:

```bash
pip install -r analysis/requirements.txt && pip install --no-deps -e .
```

## Full pipeline

| Step | Command | Writes | Time (2 CPUs) |
|---|---|---|---|
| 1. Mutation testing, core suite | `python analysis/mutation_matrix.py` | `out/mutation_matrix.json` | ~2 min |
| 2. Mutation testing, generated suite | `python analysis/mutation_generated.py` | `out/mutation_generated.json` | ~1 h |
| 3. Bootstrap CIs, categories, conditions, metric ablation, ranking agreement across seeds, cost; figures | `python analysis/analyze.py` | `out/analysis.json`, `out/fig_ci.pdf`, `fig_categories.pdf`, `fig_calls.pdf` | ~1 min |
| 4. History figure | `python analysis/fig_history.py` | `out/fig_history.pdf` | seconds |
| 5. Ground-truth ablation and corpus statistics | `python analysis/gt_ablation.py` | `out/gt_ablation.json` | ~1 min |
| 6. Feature baselines (reference: 24 surface-agnostic features; official split, 5 random splits, LOFO) | `python analysis/learned_baselines.py` | `out/learned_baselines.json` | ~25 min |
| 7. Sequence baselines (TF-IDF + LR, JAX transformer) | `python analysis/sequence_baselines.py` | `out/sequence_baselines.json` | ~1.5 h |
| 8. Feature ablation and surface probe | `python analysis/feature_ablation.py` | `out/feature_ablation.json` | ~40 min |
| 9. Tag-masking ablation (see below) | three commands below | `out/learned_baselines_allfeatures.json`, `out/learned_baselines_tagged.json` | ~15 min |
| 10. Tables and numbers for the paper | `python analysis/make_tables.py` | `paper/tmlr/gen/*.tex` | seconds |
| 11. Figures into the paper | `cp analysis/out/fig_*.pdf paper/tmlr/figures/` | | |

Then build the paper as described in [`paper/README.md`](../paper/README.md).

Step 9, the tag-masking ablation, compares the same 26-feature models on task inputs with and without the harness tag:

```bash
python analysis/learned_baselines.py --features all --skip-iid --out analysis/out/learned_baselines_allfeatures.json
python -m tracegap.tasks build --keep-tag --out analysis/out/tasks_tagged
python analysis/learned_baselines.py --features all --skip-iid --tasks analysis/out/tasks_tagged \
    --out analysis/out/learned_baselines_tagged.json
```

## Inputs

- `results/results.json`, `results/generated/results.json`: released results (core and generated suites).
- `results/seeds/seed2`, `seed3`: two extra generated suites for ranking agreement, produced with
  `SUITE=generated GEN_N=100 GEN_SEED=2 OUT=results/seeds/seed2 scripts/run_all.sh` (and seed 3).
- `results/generated/runs/`, `results/runs/`: repeated full runs for the stability analysis
  (`python scripts/stability.py results/generated/runs/run*.json`).
- `hf-dataset/data/*.parquet` (corpus) and `hf-dataset/tasks/*.parquet` (learning tasks; rebuild with
  `python -m tracegap.tasks build`).

## Numbers written directly in the paper text

`make_tables.py` produces every table and most numbers. A few are written in the text and checked by hand against
these sources:

- core-suite category counts: `out/analysis.json` (data of Figure `fig:categories`);
- per-surface unstable counts and the 104 + 44 split: `results/generated/STABILITY.md`;
- Stable/Stress case counts per surface: `tracegap/tiers.py` applied to the released results;
- release counts: `results/HISTORY.md`;
- ADK's 77.7% (Stable) / 14.3% (Stress events) / 99.2% (Stress spans): `results/LEADERBOARD.md`;
- "118 of the 200 generated scenarios are Stress": `tracegap/tiers.py` on `results/generated/results.json`;
- "11–18 points wide" (bootstrap interval widths, rounded): `out/analysis.json` (`bootstrap.ci`);
- "above .96" (T2 once recorded statuses are added): `out/feature_ablation.json`;
- the six defective CrewAI cases: `results/results.json`;
- 11,060 task examples (sequence inputs identical with and without the tag): `hf-dataset/tasks/*.parquet`.
