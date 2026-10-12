#!/bin/bash
# RQ1 step 0: reproduce each forecasting repository's own example before its model is used (CLAUDE.md fidelity rule 3).
#   research/forecasting_rq1/scripts/00_reproduce.sh   -> evidence/forecasting/reproduce/{chronos_bolt,timesfm,chronos2}/ + SUMMARY.json
# Upstream code runs unchanged from its own checkout (~/.dhakaflow/upstream/<repo>); its outputs go to our evidence folder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
UP="$HOME/.dhakaflow/upstream"; EV="$ROOT/evidence/forecasting/reproduce"; mkdir -p "$EV"/{chronos_bolt,timesfm,chronos2}
VENV="$HOME/.dhakaflow/venvs/chronos-eval"                                  # the evaluation script's own extras, apart from the backend
[ -x "$VENV/bin/python" ] || { python3 -m venv --system-site-packages "$VENV"; "$VENV/bin/pip" -q install "gluonts[pro]~=0.16" "typer" "datasets>=3.0,<5"; }
"$VENV/bin/pip" freeze | grep -iE "^(gluonts|datasets|chronos-forecasting|torch|timesfm)==" > "$EV/versions.txt"

# 1. Chronos-Bolt-small: the repo's evaluate.py on two datasets of its own zero-shot config, against its published CSV
( cd "$UP/chronos-forecasting/scripts/evaluation" && git -C "$UP/chronos-forecasting" rev-parse HEAD > "$EV/chronos_bolt/upstream_commit.txt"
  "$VENV/bin/python" evaluate.py chronos-bolt "$ROOT/research/forecasting_rq1/configs/chronos_bolt_reproduce.yaml" "$EV/chronos_bolt/ours.csv" \
     --model-id amazon/chronos-bolt-small --device cpu --torch-dtype float32 --batch-size 64 ) > "$EV/chronos_bolt/run.log"
cp "$UP/chronos-forecasting/scripts/evaluation/results/chronos-bolt-small-zero-shot.csv" "$EV/chronos_bolt/published.csv"

# 2. TimesFM 2.5: the repo's own example (global temperature) run unchanged in a copy, against the output it ships
T="$(mktemp -d)"; cp -R "$UP/timesfm/timesfm-forecasting/examples/global-temperature/." "$T/"; cp "$T/output/forecast_output.csv" "$EV/timesfm/published.csv"
git -C "$UP/timesfm" rev-parse HEAD > "$EV/timesfm/upstream_commit.txt"
( cd "$T" && rm -f output/forecast_output.csv && python run_forecast.py ) > "$EV/timesfm/run.log" 2>&1
cp "$T/output/forecast_output.csv" "$EV/timesfm/ours.csv"

# 3. Chronos-2: the README quick-start (no per-dataset table is published for Chronos-2, so shapes and outputs are recorded)
python research/forecasting_rq1/scripts/chronos2_quickstart.py > "$EV/chronos2/run.log" 2>&1

python research/forecasting_rq1/scripts/compare_reproductions.py
