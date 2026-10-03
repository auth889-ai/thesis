"""The user-data scripts an instance runs. Each finds the AMI's PyTorch interpreter, pulls its
inputs from S3, does its work, uploads logs and results, writes a DONE marker and shuts down; a hard
watchdog shuts the instance down after MAXH hours no matter what, and the instance is launched with
`--instance-initiated-shutdown-behavior terminate`, so a finished OR crashed job stops billing.

Placeholders (@NAME@, @BUCKET@, ...) are filled by `render`, which refuses to leave one behind."""
from __future__ import annotations


def render(script: str, **subs: str) -> str:
    for k, v in subs.items():
        script = script.replace(f"@{k}@", v)
    assert "@" not in script.split("aws s3")[0], "unsubstituted placeholder remains"
    return script


# The benchmark job: the pinned BasicTS harness, METR-LA / PEMS-BAY from S3, the OFFICIAL configs
# unmodified except dataset name and epochs; every log, checkpoint and metric goes back to S3.
JOB_SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@; SHA=@SHA@; MODELS="@MODELS@"; DATASETS="@DATASETS@"; EPOCHS=@EPOCHS@
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &          # hard watchdog
aws s3 cp s3://$BUCKET/jobs/$NAME/ /home/ec2-user/in/ --recursive || true
cd /home/ec2-user
git clone -q https://github.com/GestaltCogTeam/BasicTS.git bts && cd bts && git checkout -q $SHA
# Find the AMI's prepared PyTorch interpreter instead of hard-coding a path: DLAMI variants place it
# at /opt/conda, /opt/pytorch or a venv, and guessing wrong wastes a whole instance. Pick the first
# interpreter that can actually `import torch`, and dump the layout if none can.
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /opt/conda/bin/python \
         /usr/local/bin/python3 /usr/bin/python3 $(ls -d /opt/*/bin/python /opt/*/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
if [ -z "$PY" ]; then
  echo "NO TORCH INTERPRETER FOUND — layout follows so the next launch can target it"
  ls -la /opt/ ; ls -la /opt/*/bin/python* 2>/dev/null; which -a python python3
  find /opt /usr/local -maxdepth 4 -name "python3*" -type f 2>/dev/null | head -20
  aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
  shutdown -h now
fi
echo "USING INTERPRETER: $PY"
$PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
$PY -m pip install -q easy-torch==1.3.3 easydict packaging setproctitle scikit-learn tables sympy tqdm tensorboard
$PY -c "import pandas,tables;print('pandas',pandas.__version__,'tables ok')"
mkdir -p datasets/raw_data
for D in $DATASETS; do
  mkdir -p datasets/raw_data/$D
  cp /home/ec2-user/in/$D/* datasets/raw_data/$D/ 2>/dev/null || true
  $PY scripts/data_preparation/$D/generate_training_data.py || echo "PREP FAILED $D"
done
# model-specific extras: STD-MAE needs two packages and the authors' released mask checkpoints (uploaded as in/mask_save)
if echo " $MODELS " | grep -q " STDMAE "; then
  $PY -m pip install -q positional_encodings==6.0.1 timm==0.6.7 || echo "STDMAE DEPS FAILED"
  mkdir -p baselines/STDMAE/mask_save && cp /home/ec2-user/in/mask_save/*.pt baselines/STDMAE/mask_save/ 2>/dev/null || echo "NO MASK CHECKPOINTS"
fi
for D in $DATASETS; do for M in $MODELS; do
  CFG=baselines/$M/$D.py
  [ -f "$CFG" ] || CFG=baselines/$M/${M}_${D}.py        # some baselines name their configs <MODEL>_<DATASET>.py (STDMAE)
  [ -f "$CFG" ] || { echo "no config $CFG"; continue; }
  sed -i "s/^NUM_EPOCHS = .*/NUM_EPOCHS = $EPOCHS/" $CFG || true
  # evaluate the 5-minute horizon as well (official default is [3, 6, 12] = 15/30/60 min)
  # evaluate every horizon when the official config already does (PEMS flow papers report the 12-step average)
  grep -q "CFG.EVAL.HORIZONS = \[1, 2, 3" $CFG || sed -i "s/^CFG.EVAL.HORIZONS = .*/CFG.EVAL.HORIZONS = [1, 3, 6, 12]/" $CFG || true
  # DCRNN's official config calls random.randint with float bounds (-1e6, 1e6); Python >= 3.10 raises
  # TypeError. Same call with integer bounds; the value is a throwaway seed and nothing else changes.
  sed -i "s/random.randint(-1e6, 1e6)/random.randint(-1000000, 1000000)/" $CFG || true
  echo "=== TRAIN $M $D ==="
  # per-model cap follows --max-hours (the watchdog), minus half an hour for the uploads; the old fixed
  # 3-hour cap would have killed a 100-epoch recurrent model before its final test evaluation
  timeout $((@MAXH@ * 3600 - 1800)) $PY experiments/train.py -c $CFG -g 0 2>&1 | tee /tmp/${M}_${D}.log
  aws s3 cp /tmp/${M}_${D}.log s3://$BUCKET/jobs/$NAME/logs/ || true
  # the checkpoint IS the result: without it nothing can be re-run or served for inference
  aws s3 sync checkpoints/ s3://$BUCKET/jobs/$NAME/checkpoints/ \
      --exclude "*" --include "*.pt" --include "test_results.npz" --include "test_metrics.json" \
      --include "*.json" --include "*.py" || true
done; done
aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
shutdown -h now
"""

# A CITY JOB: the dataset the app prepared locally with the harness's own script (datasets/DF_<name>/)
# and the derived configs go up; the harness is cloned at the pinned SHA on the GPU and runs them.
# The log is synced every 20 s so the app can show the epoch counter while it trains.
CITY_SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@; SHA=@SHA@; MODELS="@MODELS@"; DSNAME=@DSNAME@
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &          # hard watchdog
( while true; do sleep 20; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/live.log >/dev/null 2>&1; done ) &
aws s3 cp s3://$BUCKET/jobs/$NAME/in/ /home/ec2-user/in/ --recursive || true
cd /home/ec2-user
git clone -q https://github.com/GestaltCogTeam/BasicTS.git bts && cd bts && git checkout -q $SHA
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /opt/conda/bin/python \
         /usr/local/bin/python3 /usr/bin/python3 $(ls -d /opt/*/bin/python /opt/*/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
[ -z "$PY" ] && { echo NO_TORCH; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/; echo FAILED > /tmp/DONE; aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE; shutdown -h now; }
$PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
$PY -m pip install -q easy-torch==1.3.3 easydict packaging setproctitle scikit-learn tables sympy tqdm tensorboard
mkdir -p datasets/$DSNAME && cp /home/ec2-user/in/datasets/* datasets/$DSNAME/
for M in $MODELS; do
  cp /home/ec2-user/in/configs/$M.py baselines/$M/$DSNAME.py
  echo "=== TRAIN $M $DSNAME ==="
  timeout 7200 $PY experiments/train.py -c baselines/$M/$DSNAME.py -g 0 2>&1 | tee /tmp/${M}_${DSNAME}.log
  aws s3 cp /tmp/${M}_${DSNAME}.log s3://$BUCKET/jobs/$NAME/logs/ || true
  aws s3 sync checkpoints/ s3://$BUCKET/jobs/$NAME/checkpoints/ --exclude "*" --include "*.pt" --include "*test_metrics.json" --include "*.log" --include "*.py" || true
done
aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
shutdown -h now
"""

# The federated experiment is the point where the ML and networking halves meet, so it ships its own
# job: it needs the measured MOSAIC link statistics on the box, not just a dataset.
FED_SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &
aws s3 cp s3://$BUCKET/jobs/$NAME/ /home/ec2-user/in/ --recursive || true
cd /home/ec2-user
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /usr/bin/python3 $(ls -d /opt/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
[ -z "$PY" ] && { echo NO_TORCH; ls -la /opt; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/; shutdown -h now; }
echo "USING $PY"; $PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
$PY -m pip install -q pandas tables
mkdir -p repo/src/pipeline/forecasting repo/results/networking repo/data/forecasting/cities/METR-LA
cp /home/ec2-user/in/federated_forecast.py repo/src/pipeline/forecasting/
cp /home/ec2-user/in/penetration_*.json repo/results/networking/ 2>/dev/null || true
cp /home/ec2-user/in/METR-LA/* repo/data/forecasting/cities/METR-LA/ 2>/dev/null || true
cd repo && touch src/pipeline/__init__.py src/pipeline/forecasting/__init__.py
$PY src/pipeline/forecasting/federated_forecast.py --self-test 2>&1 | tee /tmp/selftest.log
for CL in @CLIENTS@; do
  echo "=== federated clients=$CL ==="
  timeout 7200 $PY src/pipeline/forecasting/federated_forecast.py --data /home/ec2-user/in/metr_la.npz \
      --clients $CL --rounds @ROUNDS@ --local-epochs 1 --seed 11 2>&1 | tee /tmp/fed_c${CL}.log
  aws s3 cp /tmp/fed_c${CL}.log s3://$BUCKET/jobs/$NAME/logs/ || true
  aws s3 sync results/forecasting s3://$BUCKET/jobs/$NAME/results/ --exclude "*" --include "federated*" || true
done
aws s3 cp /tmp/selftest.log s3://$BUCKET/jobs/$NAME/logs/ || true
aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
shutdown -h now
"""

# Cross-city evaluation with the official OpenCity foundation model, on GPU because the released
# OpenCity-plus (512-dim, 6 encoder blocks, 288-step input and output) is not practical on CPU.
# Weights and datasets are the authors' released artefacts, pulled from their HuggingFace repos.
# Which dataset to evaluate lives in their conf and cannot be set on the command line (upstream
# declares -dataset_use as type=list, so argparse would split the name into characters), so the
# script rewrites that single assignment per city and restores it afterwards — their README's own
# documented procedure.
OPENCITY_SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@; OCSHA=@OCSHA@
# exported: the Python heredoc below reads it from the environment, not the shell
export CITIES="@OCDATASETS@"
OCBATCH=@OCBATCH@
# Fragmentation is the difference between fitting and not on the big-node cities.
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # older torch name
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &
aws s3 cp s3://$BUCKET/jobs/$NAME/ /home/ec2-user/in/ --recursive || true
cd /home/ec2-user
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /usr/bin/python3 $(ls -d /opt/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
[ -z "$PY" ] && { echo NO_TORCH; ls -la /opt; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/; shutdown -h now; }
echo "USING $PY"; $PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
$PY -m pip install -q fastdtw tslearn huggingface_hub pandas
git clone -q https://github.com/HKUDS/OpenCity.git oc && cd oc && git checkout -q $OCSHA
git rev-parse HEAD
mkdir -p model_weights/OpenCity
$PY - <<'EOF'
from huggingface_hub import hf_hub_download
import shutil, zipfile, pathlib, os
root = pathlib.Path('/home/ec2-user/oc')
w = hf_hub_download('hkuds/OpenCity-Plus', 'OpenCity-plus.pth')
shutil.copy2(w, root/'model_weights/OpenCity/OpenCity-plus.pth')
for name in os.environ['CITIES'].split():
    z = hf_hub_download('hkuds/OpenCity-dataset', f'{name}.zip', repo_type='dataset')
    with zipfile.ZipFile(z) as zf: zf.extractall(root/'data')
    print('extracted', name)
EOF
for CITY in $CITIES; do
  if [ ! -f "/home/ec2-user/oc/data/$CITY/${CITY}_rn_adj.npy" ]; then
    echo "MISSING_DATA $CITY — released artefacts did not download; aborting before wasting GPU time"
    aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
    echo FAILED_NO_DATA > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
    shutdown -h now
  fi
done
cp /home/ec2-user/in/_opencity_boot.py /home/ec2-user/oc/
CONF=conf/general_conf/pretrain.conf
cp $CONF /tmp/pretrain.conf.orig
for CITY in $CITIES; do
  echo "=== OpenCity zero-shot: $CITY ==="
  sed -i "s/^dataset_use *=.*/dataset_use = ['$CITY']/" $CONF
  grep '^dataset_use' $CONF
  cd model
  DF_OC_SCRIPT=/home/ec2-user/oc/model/Run.py timeout 7200 $PY /home/ec2-user/oc/_opencity_boot.py       -mode test -model OpenCity -load_pretrain_path OpenCity-plus.pth -batch_size $OCBATCH --batch_size $OCBATCH --embed_dim 512 --skip_dim 512 --enc_depth 6 2>&1 | tee /tmp/oc_${CITY}.log
  cd ..
  # PREFLIGHT: upstream copies the predictor config over anything passed with a single hyphen, so
  # a value we "set" can be silently discarded -- that is exactly how attempt 4 ran at 64 while we
  # believed it was 1. Compare what upstream PARSED against what we asked for, and mark the run.
  PARSED=$(grep -m1 "^batch_size : " /tmp/oc_${CITY}.log | awk '{print $3}')
  if [ -n "$PARSED" ] && [ "$PARSED" != "$OCBATCH" ]; then
    echo "PREFLIGHT_MISMATCH batch_size requested=$OCBATCH parsed=$PARSED" | tee -a /tmp/oc_${CITY}.log
  else
    echo "PREFLIGHT_OK batch_size=$PARSED" | tee -a /tmp/oc_${CITY}.log
  fi
  cp /tmp/pretrain.conf.orig $CONF
  aws s3 cp /tmp/oc_${CITY}.log s3://$BUCKET/jobs/$NAME/logs/ || true
done
git status --porcelain --untracked-files=no > /tmp/oc_clean.txt
aws s3 cp /tmp/oc_clean.txt s3://$BUCKET/jobs/$NAME/logs/ || true
aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
shutdown -h now
"""
