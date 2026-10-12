#!/usr/bin/env bash
# Generate the named arXiv preprint from the anonymous submission source.
set -euo pipefail
cd "$(dirname "$0")"
sed -e 's/^\\usepackage{tmlr}/\\usepackage[preprint]{tmlr}/' \
    -e 's#anonymous.4open.science/r/tracegap#github.com/pushkardg/tracegap#' \
    -e 's/The authors directed the work, reviewed and verified all results, and take full responsibility/The author directed the work, reviewed and verified all results, and takes full responsibility/' \
    tracegap_tmlr.tex > tracegap_preprint.tex
for f in tracegap_tmlr tracegap_preprint; do
  pdflatex -interaction=nonstopmode "$f" >/dev/null; bibtex "$f" >/dev/null
  pdflatex -interaction=nonstopmode "$f" >/dev/null; pdflatex -interaction=nonstopmode "$f" | grep -E "^!|Output written" || true
done
