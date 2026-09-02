#!/bin/bash
# P3 arm: one graph model on the legacy BasicTS harness (official, unmodified).
# Wrapper sets: MODEL (STID | GWNET | DCRNN | STAEformer — folder names below).
# Mirrors notebooks/P3_forecasting_colab.ipynb cells 3-5 on an AWS GPU.
set -exo pipefail
cd /workspace
S3=s3://dhakaflow-train-915644996102
LEGACY_SHA=4c3e2d373c647667c2123e1591f2d79c229dfcc6

dnf install -y -q git python3.11 python3.11-pip
aws s3 cp $S3/code/p3_code.tar.gz . && tar xzf p3_code.tar.gz
aws s3 cp $S3/datasets/p2_full.tar.gz . && tar xzf p2_full.tar.gz

python3.11 -m venv venv && . venv/bin/activate
pip -q install --upgrade pip
pip -q install torch==2.0.1 --index-url https://download.pytorch.org/whl/cu118
git clone https://github.com/GestaltCogTeam/BasicTS.git BasicTS_legacy
git -C BasicTS_legacy checkout $LEGACY_SHA
# The harness's OWN requirements (easy-torch==1.3.3, numpy==1.24.4, ...) —
# latest easytorch lacks init_cfg (found the hard way on the CPU pathfinder).
pip -q install -r BasicTS_legacy/requirements.txt

# Export the P2 tensor into the legacy layout (validated adapter, cell 4).
python - <<'PYEOF'
import sys, pathlib
sys.path.insert(0, "/workspace")
from pipeline.adapters.forecasting.basicts_adapter import export_basicts_legacy_dataset
print(export_basicts_legacy_dataset(
    pathlib.Path("/workspace/p2_full"),
    pathlib.Path("/workspace/BasicTS_legacy/datasets/DhakaR1SensorGraph_legacy")))
PYEOF

# Official config as template, dataset name + node count patched (cell 5).
python /workspace/research/forecasting/make_legacy_config.py \
  --bts /workspace/BasicTS_legacy --model "$MODEL"

mkdir -p /workspace/ckpt /workspace/logs
cd /workspace/BasicTS_legacy
python experiments/train.py -c "baselines/$MODEL/DhakaR1SensorGraph_legacy.py" \
  2>&1 | tee /workspace/logs/train.log
# Persist checkpoints + result summaries for triage.
cp -r checkpoints /workspace/ckpt/ 2>/dev/null || true
