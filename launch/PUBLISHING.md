# Publishing checklist for v1.0

The repository is ready to publish; these steps need your accounts. Do them in order, because later steps cite earlier ones.

## 1. Placeholders

The GitHub and Hugging Face owner is set to `pushkardg`. The Zenodo DOI (`XXXXXXX`) is filled in by `launch/add_doi.sh` in step 3. In `launch/`, replace `<link>` with the repository URL.

## 2. GitHub and 3. Zenodo

```bash
gh auth login                      # as pushkardg
bash launch/publish.sh             # creates the repo, pushes, waits for CI, creates release v1.0.0
bash launch/add_doi.sh 10.5281/zenodo.NNNNNNN    # the concept DOI from the Zenodo record
```

`publish.sh` pauses once for the one browser step: at https://zenodo.org/account/settings/github/, sign in with GitHub, click *Sync now* and switch on `pushkardg/tracegap`. This must happen **before** the release is created, or Zenodo will not archive it. Zenodo then mints two DOIs: a concept DOI (all versions, the one to cite) and a version DOI. `.zenodo.json` supplies the title, author and description. Each later GitHub release gets its own version DOI automatically.

## 4. PyPI

```bash
python -m pip install build twine
python -m build
twine check dist/*
twine upload dist/*          # needs a PyPI account and API token
pip install tracegap && tracegap --help    # in a fresh environment
```

For later releases, consider PyPI trusted publishing from a GitHub workflow.

## 5. Hugging Face dataset

```bash
python scripts/build_dataset.py --repo https://github.com/<owner>/tracegap
huggingface-cli login
huggingface-cli upload <hf-user>/tracegap hf-dataset . --repo-type dataset
```

Then open the dataset page and check that both configurations (`default`, `tasks`) load in the viewer.

## 6. Upstream issues and pull requests

Follow `launch/issues.md` and `upstream-fixes/README.md`: open each issue, then the PR that links it. Link TraceGap in each. Once they are open, add a status column (open, acknowledged, merged) to Table `tab:upstream` in `paper/tmlr/tracegap_tmlr.tex`; add issue and PR links only in the preprint and camera-ready versions, never in the anonymous submission.

## 7. Paper

1. **Anonymous mirror for the TMLR submission.** The repository names the author (README, CITATION.cff, pyproject.toml, DATASHEET.md, LICENSE, git history). Create an anonymized copy (for example with anonymous.4open.science, which can replace names) and put its URL in `\codeurl` in `paper/tmlr/tracegap_tmlr.tex`.
2. **Preprint.** Regenerate `paper/tmlr/tracegap_preprint.tex` from the submission source (command in `paper/README.md`), replace `<owner>`, rebuild, and post it to arXiv (cs.LG or cs.SE, with the other as a cross-list). Submit the anonymous PDF to TMLR on OpenReview.

## 8. Announce

Use `launch/blog-post.md` and `launch/social.md`, then the outreach plan in `launch/outreach.md`. Aim for the first three to five external users, and record who adopts it.
