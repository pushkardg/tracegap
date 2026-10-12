# Paper

The paper is in `tmlr/` (TMLR format):

| File | What it is |
|---|---|
| `tmlr/tracegap_tmlr.tex` / `.pdf` | Anonymous version for double-blind submission (`\usepackage{tmlr}`); the code link points to an anonymized mirror (`\codeurl`) |
| `tmlr/tracegap_preprint.tex` / `.pdf` | Named preprint for arXiv (`\usepackage[preprint]{tmlr}`, code link to GitHub). Generated from the submission source by `tmlr/make_preprint.sh` |
| `tmlr/gen/` | All tables and most data-derived numbers, written by `analysis/make_tables.py` (do not edit by hand) |
| `tmlr/figures/` | Figures, copied from `analysis/out/` |

Rebuild everything from the released results with the commands in [`analysis/README.md`](../analysis/README.md), then:

```bash
paper/tmlr/make_preprint.sh      # regenerates the preprint source and builds both PDFs
```

An earlier short version of the paper (v0.2) is in the git history; it is superseded and its numbers are out of date.
