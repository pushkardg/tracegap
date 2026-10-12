#!/usr/bin/env bash
# Run every framework in its own pinned virtualenv, then merge the results.
#   scripts/run_all.sh            # create envs if missing, run, merge, report
#   ENV_DIR=/tmp/envs scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_DIR="${ENV_DIR:-.envs}"
SUITE="${SUITE:-core}"          # core | generated
GEN_N="${GEN_N:-200}"; GEN_SEED="${GEN_SEED:-1}"
if [ "$SUITE" = "generated" ]; then DEFAULT_OUT=results/generated; else DEFAULT_OUT=results; fi
OUT="${OUT:-$DEFAULT_OUT}"      # override to keep extra runs (other seeds) separate
PY="${PYTHON:-python3}"
mkdir -p "$ENV_DIR" "$OUT/parts" "$OUT/traces"
declare -A ADAPTERS=(
  [core]="langgraph openai-agents pydantic-ai autogen"
  [smolagents]="smolagents"
  [llamaindex]="llamaindex"
  [semantic-kernel]="semantic-kernel"
  [google-adk]="google-adk"
  [crewai]="crewai"
)
parts=()
for env in core smolagents llamaindex semantic-kernel google-adk crewai; do
  venv="$ENV_DIR/$env"
  if [ ! -x "$venv/bin/python" ]; then
    echo "== creating $venv"
    "$PY" -m venv "$venv"
    "$venv/bin/pip" install -q -r "envs/$env.txt"
    "$venv/bin/pip" install -q --no-deps -e .
  fi
  echo "== running $env"
  "$venv/bin/python" -m tracegap.cli --adapters ${ADAPTERS[$env]} --suite "$SUITE" --n "$GEN_N" --seed "$GEN_SEED" \
    --out "$OUT/parts/$env.json" --traces "$OUT/traces"
  parts+=("$OUT/parts/$env.json")
done
python3 -m tracegap.merge "$OUT/results.json" "${parts[@]}"
if [ "$SUITE" = "core" ]; then
  python3 -m tracegap.report "$OUT/results.json" --out "$OUT/CORE.md" --leaderboard "$OUT/LEADERBOARD.md"
else
  python3 -m tracegap.report "$OUT/results.json" --out "$OUT/LEADERBOARD.md"
  if [ "$OUT" = "$DEFAULT_OUT" ]; then
    python3 -m tracegap.report results/results.json --out results/CORE.md --generated "$OUT/results.json" --leaderboard results/LEADERBOARD.md
  fi
fi
if [ "$SUITE" = "core" ] && [ "$OUT" = "$DEFAULT_OUT" ]; then
  python3 -m tracegap.site results/results.json --standalone --out site/index.html
fi
