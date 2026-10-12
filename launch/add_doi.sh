#!/usr/bin/env bash
# Put the Zenodo concept DOI into the README, CITATION.cff and dataset card, then push.
#
#   bash launch/add_doi.sh 10.5281/zenodo.1234567
set -euo pipefail
DOI="${1:?usage: launch/add_doi.sh 10.5281/zenodo.NNNNNNN (the concept DOI)}"
[[ "$DOI" =~ ^10\.5281/zenodo\.[0-9]+$ ]] || { echo "Expected 10.5281/zenodo.<digits>, got $DOI"; exit 1; }
N="${DOI##*.}"
cd "$(git rev-parse --show-toplevel)"

sed -i.bak "s/zenodo\.XXXXXXX/zenodo.$N/g" README.md && rm -f README.md.bak
python - "$DOI" <<'EOF'
import re, sys
from pathlib import Path
doi = sys.argv[1]
p = Path("CITATION.cff"); s = p.read_text()
s = re.sub(r"# After the first GitHub release.*\n# doi: .*\n", "", s)
if not re.search(r"^doi:", s, re.M):
    s = re.sub(r"^version:", f"doi: {doi}\nversion:", s, count=1, flags=re.M)
p.write_text(s)
p = Path("hf-dataset/README.md"); s = p.read_text()
if "doi    =" not in s:
    s = s.replace("  url    = {https://github.com", "  doi    = {" + doi + "},\n  url    = {https://github.com", 1)
p.write_text(s)
p = Path("scripts/build_dataset.py"); s = p.read_text()  # keep the card's BibTeX on rebuild
if "doi    =" not in s:
    s = s.replace("  url    = {{{repo}}}", "  doi    = {{" + doi + "}},\n  url    = {{{repo}}}", 1)
p.write_text(s)
EOF
grep -n "zenodo\|doi" README.md CITATION.cff hf-dataset/README.md | head -20
git add README.md CITATION.cff hf-dataset/README.md scripts/build_dataset.py
git commit -qm "Add Zenodo DOI $DOI" && git push origin main
echo "Done. Also add the DOI to the preprint (paper/tmlr) and the Hugging Face dataset page when you upload it."
