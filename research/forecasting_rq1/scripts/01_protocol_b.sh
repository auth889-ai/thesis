#!/bin/bash
# RQ1 steps 1-3: Protocol B on METR-LA (207 roads) and PEMS-BAY (325 roads), seeds 11, 23, 37, every model (baselines, trees,
# Chronos-Bolt, Chronos-2, TimesFM 2.5, our checkpoints). A block that already holds every model is kept; one without
# Chronos-Bolt or TimesFM (older runs) is run again. Then the RQ1 stages.   research/forecasting_rq1/scripts/01_protocol_b.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT/backend"; mkdir -p ../results/forecasting/rq1/logs
complete() { python - "$1" <<'PY'
import sys, numpy as np, pathlib
p = pathlib.Path(sys.argv[1]); ok = p.exists() and {"pred_chronos", "pred_chronos2", "pred_timesfm", "pred_persistence"} <= set(np.load(p).files)
sys.exit(0 if ok else 1)
PY
}
for ds in METR-LA PEMS-BAY; do n=$([ $ds = METR-LA ] && echo 207 || echo 325); for s in 11 23 37; do
  b="../results/forecasting/protocol_b/${ds}_test_w120_n${n}_s${s}.npz"
  if complete "$b"; then echo "kept $b"; continue; fi
  echo "run $ds seed $s ($(date +%H:%M))"
  /usr/bin/time -p python -m core.ml.forecasting.evaluation.evaluate_models --dataset $ds --windows 120 --seed $s --max-nodes 0 --zero-shot chronos,chronos2,timesfm > ../results/forecasting/rq1/logs/${ds}_s${s}.log 2>&1
done; done
for stage in rescore transfer dhaka character summary; do echo "stage $stage ($(date +%H:%M))"; python -m core.ml.forecasting.transfer_dhaka.run $stage; done
echo "RQ1 DONE"
