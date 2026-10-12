# Getting TraceGap used: outreach plan

The aim is genuine use: maintainers running it in CI, vendors citing it, researchers building on the corpus. Do the steps in order; each one makes the next more credible.

## Week 1: publish

1. **GitHub.** Push the repo and turn on GitHub Pages for `site/` (Settings → Pages → deploy from branch, `/site` folder). Pages serves `site/index.html` as the public leaderboard.
2. **Release v1.0.0, then Zenodo.** Link the repo in Zenodo (GitHub integration) *before* creating the release; the release then gets a DOI automatically. Add the DOI to `CITATION.cff` and the README badge.
3. **PyPI.** `python -m build && twine upload dist/*`. `pip install tracegap` removes the biggest barrier to trying it.
4. **Hugging Face.** Create a dataset repo (`pushkardg/tracegap`) and upload `hf-dataset/` (`huggingface-cli upload pushkardg/tracegap hf-dataset . --repo-type dataset`). The dataset card is already written.
5. **arXiv.** Post the paper with the repo, DOI and dataset links. Use cs.SE as primary category, with cs.AI and cs.LG cross-lists. You need an arXiv endorser for cs.SE if you haven't posted there before; a co-reviewer or past collaborator can endorse.

## Week 1–2: upstream (highest value)

6. **Open the issues, then the PRs** (`issues.md`, `../upstream-fixes/README.md`), one project at a time. Respond quickly to review comments. A merged fix that names TraceGap in its description is the strongest evidence of use you can get.
7. **OpenTelemetry GenAI SIG.** Post the cancellation note from `issues.md`. If the semantic conventions adopt guidance, TraceGap becomes the test for it.

## Week 2–3: people who would actually run it

Send short, specific messages: one finding that concerns them, plus the one-line command to reproduce it. Don't send a generic announcement.

| Who | Why they care | What to offer |
|---|---|---|
| Langfuse, Arize Phoenix, LangSmith, Logfire, Braintrust, Datadog LLM Observability, Helicone, Traceloop/OpenLLMetry | Their UIs display these spans; a cancelled call shown as success is their user's problem | The cancellation finding; ask whether they want an adapter for their SDK, or a TraceGap check in their CI |
| OpenInference maintainers (Arize) | Two of their instrumentors are measured; one is incompatible with older smolagents | Results for their instrumentors; an offer to add more |
| Framework maintainers (all nine) | The GitHub Action and pytest helper drop into their CI | A one-file PR adding `tracegap.testing` with known gaps as xfail. Offer it only after the bug-fix PR has gone well. |
| Agent reliability and provenance researchers (authors of the provenance survey and of TRAIL; see `docs/PRIOR_ART.md`) | They need ground-truth traces | The labeled corpus on Hugging Face |

Template (keep it under 120 words):

> Hi <name>, I built TraceGap, a small benchmark that checks whether agent frameworks' traces match what actually ran (scripted models, no API keys, runs in minutes). One result that touches <product>: when a tool call is cancelled, <framework>'s `execute_tool` span is exported with an unset status, so it shows as successful. <one sentence on the fix PR>. Results and the command to reproduce: <link>. If it's useful, I'm happy to add an adapter for <their SDK>, or help wire the GitHub Action into your CI.

## Ongoing

8. **The weekly CI job** (`latest` in `.github/workflows/ci.yml`) runs the four core-environment frameworks at their latest releases against the released results. When a release fixes or breaks something, post a short update. Each one is a natural reason for people to look again.
9. **Awesome lists.** Send PRs to curated lists on LLM agents, LLM observability and AI evaluation. Pick lists with recent commits.
10. **Talks.** The cancellation finding is a self-contained 15-minute talk: what a trace promises, how it breaks, and how to test it.

## What not to do

- Don't buy or swap stars, or ask friends to star it. Inflated metrics are easy to spot and undermine everything else.
- Don't overstate the findings. Most gaps are design choices, and the README says so. That fairness is why maintainers will engage.
- Don't open the CI-integration PR before the bug-fix PR has landed well.
