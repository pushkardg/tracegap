#!/usr/bin/env bash
# Publish TraceGap on GitHub and archive the release on Zenodo (which mints the DOI).
#
#   bash launch/publish.sh
#
# Run from the repository root. Needs: git, the GitHub CLI (`gh auth login` as the
# repository owner), and a Zenodo account (sign in to zenodo.org with GitHub).
# Safe to re-run: steps that are already done are skipped.
set -euo pipefail

OWNER="${OWNER:-pushkardg}"
REPO="${REPO:-tracegap}"
VERSION="${VERSION:-1.0.0}"
TAG="v$VERSION"
SLUG="$OWNER/$REPO"

say() { printf '\n==> %s\n' "$*"; }
pause() { read -r -p "    $* Press Enter to continue... " _; }

cd "$(git rev-parse --show-toplevel)"

say "Checking prerequisites"
gh auth status >/dev/null || { echo "Run: gh auth login"; exit 1; }
[ "$(gh api user -q .login)" = "$OWNER" ] || { echo "gh is logged in as $(gh api user -q .login), not $OWNER"; exit 1; }
#[ -z "$(git status --porcelain)" ] || { echo "Commit or stash local changes first."; git status --short; exit 1; }
[ "$(git branch --show-current)" = "main" ] || { echo "Switch to the main branch first."; exit 1; }
grep -q "^version: $VERSION" CITATION.cff || { echo "CITATION.cff version is not $VERSION"; exit 1; }
grep -q "\"version\": \"$VERSION\"" .zenodo.json || { echo ".zenodo.json version is not $VERSION"; exit 1; }
python -c 'import json; json.load(open(".zenodo.json"))'

say "1/5  Creating https://github.com/$SLUG and pushing main"
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$SLUG" --public --source . --remote origin \
    --description "The agent tracing correctness benchmark: does your agent framework record what actually happened?"
fi
git push -u origin main
gh repo edit "$SLUG"  \
  --add-topic llm-agents --add-topic observability --add-topic opentelemetry \
  --add-topic benchmark --add-topic tracing --add-topic dataset

say "2/5  Turning on Zenodo archiving (one-time, in the browser)"
cat <<EOF
    1. Open https://zenodo.org/account/settings/github/ (log in with GitHub; authorize Zenodo).
    2. Click "Sync now" and switch ON the toggle next to $SLUG.
    Do not create the release on GitHub yourself; this script does it next.
EOF
pause "When $SLUG shows as ON in Zenodo,"

say "3/5  Waiting for CI on main to pass"
sleep 10
run_id="$(gh run list -R "$SLUG" --branch main --workflow ci.yml --limit 1 --json databaseId -q '.[0].databaseId' || true)"
if [ -n "$run_id" ]; then
  gh run watch "$run_id" -R "$SLUG" --exit-status || { echo "CI failed; fix it before releasing."; exit 1; }
else
  echo "    (no CI run found; check the Actions tab before continuing)"; pause "If CI is green,"
fi

say "4/5  Creating the release $TAG (Zenodo archives it automatically)"
today="$(date +%F)"
if ! grep -q "^date-released: $today" CITATION.cff; then
  sed -i.bak "s/^date-released: .*/date-released: $today/" CITATION.cff && rm -f CITATION.cff.bak
  git commit -qm "Release $TAG" CITATION.cff && git push origin main
fi
if ! gh release view "$TAG" -R "$SLUG" >/dev/null 2>&1; then
  gh release create "$TAG" -R "$SLUG" --target main --title "TraceGap $TAG" \
    --notes-file launch/release-notes.md paper/tmlr/tracegap_preprint.pdf
fi
# Floating major tag for the GitHub Action (`uses: $SLUG@v1`)
git fetch -q origin --tags
git tag -f "v${VERSION%%.*}" "$TAG" && git push -f origin "v${VERSION%%.*}"

say "5/5  Getting the DOI"
cat <<EOF
    Zenodo takes a few minutes. Open https://zenodo.org/account/settings/github/repository/$SLUG
    (or search zenodo.org for "TraceGap"). The record shows two DOIs:
      - "Cite all versions" = the CONCEPT DOI   <- use this one
      - the DOI at the top  = this version only
    Then run:   bash launch/add_doi.sh 10.5281/zenodo.NNNNNNN   (the concept DOI)
EOF
