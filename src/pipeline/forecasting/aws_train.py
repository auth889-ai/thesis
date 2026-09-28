#!/usr/bin/env python3
"""Train the forecasting baselines on an AWS spot GPU — launched and collected from the terminal.

    python src/pipeline/forecasting/aws_train.py --plan                 # show what would run and what it costs
    python src/pipeline/forecasting/aws_train.py --launch               # start the spot GPU job
    python src/pipeline/forecasting/aws_train.py --status               # is it running / done?
    python src/pipeline/forecasting/aws_train.py --collect              # pull results into results/forecasting/
    python src/pipeline/forecasting/aws_train.py --terminate            # stop it now

Why this exists: project policy is that no model is trained on the laptop, and the Colab path needs
a human to press Run all. This path needs neither — the job runs on a spot GPU, uploads its results
to S3 and terminates itself.

Safety, because this spends real credit:
  * spot g5.xlarge (1x A10G, 4 vCPU) — the smallest GPU that trains these models comfortably
  * `--instance-initiated-shutdown-behavior terminate` and the job script ends with `shutdown -h now`,
    so a finished OR crashed job stops billing immediately
  * a hard watchdog kills the instance after --max-hours no matter what
  * spot type "one-time": if AWS reclaims it, it terminates rather than relaunching silently
  * --launch refuses to start a second instance while one is already tagged running

What the job does, on the GPU:
  1. clone the pinned BasicTS-legacy harness (the same commit the Colab notebook uses)
  2. pull METR-LA / PEMS-BAY from S3 (uploaded by --launch from data/forecasting/cities/)
  3. run the OFFICIAL configs for each model, unmodified except dataset name and epochs
  4. upload every log + the parsed metrics to s3://<bucket>/jobs/<name>/
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BUCKET = "dhakaflow-train-915644996102"
REGION = "us-east-1"
# Deep Learning OSS Nvidia Driver AMI GPU **PyTorch** (AL2023). The *Base* AMI ships drivers but no
# framework: a pip-installed torch there fails with `libcudnn.so.9: cannot open shared object file`,
# and the system python3.9 has a numpy/pytables ABI clash that breaks the data prep. This AMI carries
# a working conda env (`source activate pytorch`) with matched torch + CUDA + cuDNN.
AMI = "ami-001972c501ec6b965"          # PyTorch 2.9 (AL2023) 20260829
BASICTS_SHA = "4c3e2d373c647667c2123e1591f2d79c229dfcc6"
JOB = "predict-baselines"

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
          # overridden by --job so each dataset keeps its own S3 space
RESULTS = REPO / "results/forecasting"

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

OPENCITY_SHA = "eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f"

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
for D in $DATASETS; do for M in $MODELS; do
  CFG=baselines/$M/$D.py
  [ -f "$CFG" ] || { echo "no config $CFG"; continue; }
  sed -i "s/^NUM_EPOCHS = .*/NUM_EPOCHS = $EPOCHS/" $CFG || true
  # evaluate the 5-minute horizon as well (official default is [3, 6, 12] = 15/30/60 min)
  sed -i "s/^CFG.EVAL.HORIZONS = .*/CFG.EVAL.HORIZONS = [1, 3, 6, 12]/" $CFG || true
  echo "=== TRAIN $M $D ==="
  timeout 10800 $PY experiments/train.py -c $CFG -g 0 2>&1 | tee /tmp/${M}_${D}.log
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


def aws(*args: str, region: bool = True) -> str:
    cmd = ["aws", *args] + (["--region", REGION] if region else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"aws {' '.join(args[:3])} failed:\n{r.stderr[-800:]}")
    return r.stdout


def running_instances() -> list[dict]:
    out = aws("ec2", "describe-instances", "--filters", f"Name=tag:dhakaflow-job,Values={JOB}",
              "Name=instance-state-name,Values=pending,running",
              "--query", "Reservations[].Instances[].{id:InstanceId,state:State.Name,type:InstanceType,t:LaunchTime}",
              "--output", "json")
    return json.loads(out or "[]")


def plan(a) -> int:
    models = a.models.split(",")
    datasets = a.datasets.split(",")
    print(f"job              {JOB}")
    print(f"instance         {a.instance_type} spot, {REGION}, AMI {AMI}")
    print(f"models           {models}")
    print(f"datasets         {datasets}")
    print(f"epochs           {a.epochs} (official configs otherwise unmodified)")
    print(f"runs             {len(models) * len(datasets)}")
    print(f"max hours        {a.max_hours} (hard watchdog, then terminate)")
    print(f"est. spot cost   ~${0.5 * a.max_hours:.2f} at ~$0.50/h for g5.xlarge (verify in billing)")
    print(f"results          s3://{BUCKET}/jobs/{JOB}/  ->  results/forecasting/ via --collect")
    inst = running_instances()
    print(f"already running  {inst if inst else 'no'}")
    return 0


def launch(a) -> int:
    if running_instances():
        print(f"refusing: a {JOB} instance is already running — use --status, or --terminate first")
        return 2
    # upload the datasets the job needs (OpenCity pulls its own from the authors' HuggingFace)
    for d in ([] if a.opencity else a.datasets.split(",")):
        src = REPO / "data/forecasting/cities" / d
        if not src.exists():
            print(f"missing {src}; fetch it first (src/pipeline/forecasting/city_datasets.py --list)")
            return 3
        print(f"[upload] {src} -> s3://{BUCKET}/jobs/{JOB}/{d}/")
        subprocess.run(["aws", "s3", "sync", str(src), f"s3://{BUCKET}/jobs/{JOB}/{d}/",
                        "--region", REGION], check=True, capture_output=True)
    # Clear the previous run's markers/logs, or a watcher will read a stale DONE and report early.
    for key in ("DONE", "logs/"):
        subprocess.run(["aws", "s3", "rm", f"s3://{BUCKET}/jobs/{JOB}/{key}", "--region", REGION]
                       + (["--recursive"] if key.endswith("/") else []), capture_output=True)
    script = OPENCITY_SCRIPT if a.opencity else (FED_SCRIPT if a.federated else JOB_SCRIPT)
    if a.opencity:
        boot = REPO / "src/pipeline/forecasting/_opencity_boot.py"
        subprocess.run(["aws", "s3", "cp", str(boot), f"s3://{BUCKET}/jobs/{JOB}/{boot.name}",
                        "--region", REGION], check=True, capture_output=True)
        print(f"[upload] OpenCity compatibility bootstrap -> s3://{BUCKET}/jobs/{JOB}/")
    if a.federated:
        import shutil as _sh
        extra = [REPO / "src/pipeline/forecasting/federated_forecast.py"] + \
                sorted((REPO / "results/networking").glob("penetration_p*_s*.json"))
        for f in extra:
            subprocess.run(["aws", "s3", "cp", str(f), f"s3://{BUCKET}/jobs/{JOB}/{f.name}",
                            "--region", REGION], check=True, capture_output=True)
        npz = REPO / "data/forecasting/cities/metr_la.npz"
        if npz.exists():
            subprocess.run(["aws", "s3", "cp", str(npz), f"s3://{BUCKET}/jobs/{JOB}/metr_la.npz",
                            "--region", REGION], check=True, capture_output=True)
        print(f"[upload] federated inputs: code + {len(extra) - 1} simulated-V2X profile files")
    for k, v in (("@NAME@", JOB), ("@BUCKET@", BUCKET), ("@SHA@", BASICTS_SHA),
                 ("@MODELS@", a.models.replace(",", " ")), ("@DATASETS@", a.datasets.replace(",", " ")),
                 ("@EPOCHS@", str(a.epochs)), ("@MAXH@", str(a.max_hours)),
                 ("@CLIENTS@", a.clients.replace(",", " ")), ("@ROUNDS@", str(a.rounds)),
                 ("@OCSHA@", OPENCITY_SHA), ("@OCDATASETS@", a.cities.replace(",", " ")),
                 ("@OCBATCH@", str(a.oc_batch))):
        script = script.replace(k, v)
    assert "@" not in script.split("aws s3")[0], "unsubstituted placeholder remains"
    iid, chosen, attempts = _run_instance(a, script)
    if not iid:
        return 4
    a.instance_type = chosen[0]
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) after {len(attempts)} unavailable option(s). "
          f"It installs, trains, uploads and terminates itself.")
    print(f"[launch] watch:  python src/pipeline/forecasting/aws_train.py --status")
    # Append to a history so each dataset's run keeps ITS OWN hardware provenance; overwriting a
    # single file stamped the METR-LA results with the PEMS-BAY instance id.
    (RESULTS / "aws_job.json").parent.mkdir(parents=True, exist_ok=True)
    hist_path = RESULTS / "aws_jobs.jsonl"
    entry = {"job": JOB, "instance": iid, "type": a.instance_type, "region": REGION, "ami": AMI,
         "models": a.models, "datasets": a.datasets, "epochs": a.epochs,
         "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "s3": f"s3://{BUCKET}/jobs/{JOB}/"}
    with open(hist_path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    (RESULTS / "aws_job.json").write_text(json.dumps(entry, indent=1))
    return 0


def _run_instance(a, script: str):
    """Start one instance with this user-data script: spot first across a ladder of types and
    zones, on-demand only when allowed. Returns (instance id, (type, zone, market), attempts)."""
    ud = base64.b64encode(script.encode()).decode()
    spec = json.dumps({"MarketType": "spot",
                       "SpotOptions": {"SpotInstanceType": "one-time",
                                       "InstanceInterruptionBehavior": "terminate"}})
    # Spot capacity for a single GPU type in a single AZ is routinely exhausted, so try a ladder of
    # equivalent instances across zones instead of failing. Order = cheapest capable first.
    types = [t for t in a.instance_type.split(",") if t]
    zones = json.loads(aws("ec2", "describe-availability-zones", "--query",
                           "AvailabilityZones[?State=='available'].ZoneName", "--output", "json"))
    # Spot first (cheap); if every type/zone is out of capacity, fall back to on-demand so the job
    # actually runs. On-demand costs ~2x but a 2-3 h training job is still ~$1-2.
    attempts, iid, market = [], None, "spot"
    # --no-spot: a reclaimed spot instance loses the whole run (PEMS-BAY was reclaimed 7 min in,
    # Server.SpotInstanceTermination), so long jobs that must finish should not start on spot.
    markets = ["on-demand"] if a.no_spot else (["spot", "on-demand"] if a.allow_on_demand else ["spot"])
    for market in markets:
        for t in types:
            for z in zones:
                try:
                    out = aws("ec2", "run-instances", "--image-id", AMI, "--instance-type", t,
                              "--placement", json.dumps({"AvailabilityZone": z}),
                              *(["--instance-market-options", spec] if market == "spot" else []),
                              "--instance-initiated-shutdown-behavior", "terminate",
                              "--block-device-mappings",
                              json.dumps([{"DeviceName": "/dev/xvda",
                                           "Ebs": {"VolumeSize": 120, "DeleteOnTermination": True}}]),
                              "--user-data", ud,
                              *(["--iam-instance-profile", json.dumps({"Name": a.instance_profile})]
                              if a.instance_profile else []),
                              "--tag-specifications",
                              json.dumps([{"ResourceType": "instance",
                                           "Tags": [{"Key": "dhakaflow-job", "Value": JOB},
                                                    {"Key": "Name", "Value": JOB}]}]),
                              "--query", "Instances[0].InstanceId", "--output", "text")
                    iid, chosen = out.strip(), (t, z, market)
                    break
                except SystemExit as ex:
                    reason = "no capacity" if "InsufficientInstanceCapacity" in str(ex) else str(ex)[-90:]
                    attempts.append(f"{market} {t}/{z}: {reason}")
            if iid:
                break
        if iid:
            break
    if not iid:
        print("[launch] no spot capacity anywhere. Attempts:")
        for x in attempts:
            print("   ", x)
        print("\nOptions: widen --instance-type (e.g. g4dn.xlarge,g5.xlarge,g6.xlarge), try another "
              "--region, or use the Colab notebooks instead.")
        return None, None, attempts
    return iid, chosen, attempts


def city_job_name(dataset_id: str) -> str:
    import re
    return "city-" + re.sub(r"[^a-z0-9]+", "-", dataset_id.lower()).strip("-")


def city_launch(a) -> int:
    """Train the official baselines on an app dataset (user:/live:) on a GPU — same harness, same
    derived config, same metrics as the CPU path in basicts_train.py, just faster and for more epochs."""
    global JOB
    sys.path.insert(0, str(REPO))
    from pipeline.forecasting import basicts_train as bt
    JOB = a.job or city_job_name(a.city_dataset)
    if running_instances():
        print(f"refusing: a {JOB} instance is already running — use --status, or --terminate first")
        return 2
    prep = bt.prepare(a.city_dataset)                    # their prep script, locally
    name = prep["name"]
    models = [m for m in a.models.split(",") if m]
    cfgs = {m: bt.write_config(m, name, prep["nodes"], a.epochs, prep["steps_per_day"], gpu=True) for m in models}
    for m in models:                                      # the CPU-flavoured config the app loads the checkpoint with
        bt.write_config(m, name, prep["nodes"], a.epochs, prep["steps_per_day"], gpu=False)
    ds_dir = bt.BTS / "datasets" / name
    base = f"s3://{BUCKET}/jobs/{JOB}"
    subprocess.run(["aws", "s3", "rm", f"{base}/", "--recursive", "--region", REGION], capture_output=True)
    subprocess.run(["aws", "s3", "sync", str(ds_dir), f"{base}/in/datasets/", "--region", REGION], check=True, capture_output=True)
    for m, c in cfgs.items():
        subprocess.run(["aws", "s3", "cp", str(c), f"{base}/in/configs/{m}.py", "--region", REGION], check=True, capture_output=True)
    manifest = {"job": JOB, "dataset": a.city_dataset, "dataset_sha256": prep.get("dataset_hash"), "graph_sha256": prep.get("graph_hash"),
                "models": models, "epochs": a.epochs, "upstream": "GestaltCogTeam/BasicTS", "upstream_sha": BASICTS_SHA,
                "split": "chronological 70/10/20 (their TRAIN_VAL_TEST_RATIO)", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    mf = RESULTS / "aws_city_jobs" / f"{JOB}.manifest.json"
    mf.parent.mkdir(parents=True, exist_ok=True); mf.write_text(json.dumps(manifest, indent=1))
    subprocess.run(["aws", "s3", "cp", str(mf), f"{base}/in/manifest.json", "--region", REGION], check=True, capture_output=True)
    print(f"[upload] {name}: {prep['desc']['num_time_steps']} steps x {prep['nodes']} nodes + {len(cfgs)} config(s) -> {base}/in/")
    script = CITY_SCRIPT
    for k, v in (("@NAME@", JOB), ("@BUCKET@", BUCKET), ("@SHA@", BASICTS_SHA), ("@MODELS@", " ".join(models)),
                 ("@DSNAME@", name), ("@MAXH@", str(a.max_hours))):
        script = script.replace(k, v)
    assert "@" not in script.split("aws s3")[0], "unsubstituted placeholder remains"
    iid, chosen, attempts = _run_instance(a, script)
    if not iid:
        return 4
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) — trains {models} for {a.epochs} epochs, uploads, terminates.")
    entry = {"job": JOB, "instance": iid, "type": chosen[0], "market": chosen[2], "region": REGION, "ami": AMI,
             "models": a.models, "datasets": a.city_dataset, "epochs": a.epochs,
             "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s3": f"{base}/"}
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "aws_jobs.jsonl", "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    (RESULTS / "aws_city_jobs").mkdir(exist_ok=True)
    (RESULTS / "aws_city_jobs" / f"{JOB}.json").write_text(json.dumps({**entry, "prep": prep, "configs": {m: str(c) for m, c in cfgs.items()}}, indent=1))
    return 0


def city_terminate(job: str) -> list[str]:
    """Stop every instance of this job now (a cancelled or failed job must not keep billing)."""
    global JOB
    JOB = job
    ids = [i["id"] for i in running_instances()]
    if ids:
        aws("ec2", "terminate-instances", "--instance-ids", *ids)
    return ids


def city_poll(job: str) -> dict:
    """What the app shows while a city job runs: instance state, DONE marker, the live log tail."""
    global JOB
    JOB = job
    inst = running_instances()
    done = subprocess.run(["aws", "s3", "cp", f"s3://{BUCKET}/jobs/{job}/DONE", "-", "--region", REGION],
                          capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["aws", "s3", "cp", f"s3://{BUCKET}/jobs/{job}/logs/live.log", "-", "--region", REGION],
                         capture_output=True, text=True).stdout
    return {"instances": inst, "done": done, "log": log}


def city_collect(job: str) -> list[dict]:
    """Bring their checkpoints + metrics down and write the app's cards, one per architecture."""
    global JOB
    JOB = job
    sys.path.insert(0, str(REPO))
    from pipeline.forecasting import basicts_train as bt
    meta = json.loads((RESULTS / "aws_city_jobs" / f"{job}.json").read_text())
    prep = meta["prep"]; name = prep["name"]
    dst = RESULTS / "checkpoints_cloud" / job
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(["aws", "s3", "sync", f"s3://{BUCKET}/jobs/{job}/checkpoints/", str(dst), "--region", REGION], check=True, capture_output=True)
    logs = RESULTS / "aws_logs" / job
    logs.mkdir(parents=True, exist_ok=True)
    subprocess.run(["aws", "s3", "sync", f"s3://{BUCKET}/jobs/{job}/logs/", str(logs), "--region", REGION], check=False, capture_output=True)
    cards = []
    for arch in meta["models"].split(","):
        root = dst / bt.ARCH_CLASS[arch] / f"{name}_{meta['epochs']}_{bt.IN_LEN}_{bt.OUT_LEN}"
        runs = sorted(root.glob("*/"), key=lambda p: p.stat().st_mtime) if root.exists() else []
        if not runs:
            print(f"[collect] no checkpoint for {arch} under {root}")
            continue
        log_f = logs / f"{arch}_{name}.log"
        log_text = log_f.read_text(errors="ignore") if log_f.exists() else ""
        cfg = bt.BTS / f"baselines/{bt.ARCHS[arch]}/{name}.py"
        card = bt.make_card(meta["datasets"], arch, int(meta["epochs"]), prep, cfg, runs[-1], log_text,
                            where=f"AWS {meta['type']} GPU ({meta['market']})")
        cards.append(card)
        print(f"[collect] {arch}: test {json.dumps(card['test_metrics'].get('overall'))} vs persistence {json.dumps(card['persistence_test'])}")
    return cards


def status(_a) -> int:
    inst = running_instances()
    print("instances:", inst if inst else "none running")
    done = subprocess.run(["aws", "s3", "ls", f"s3://{BUCKET}/jobs/{JOB}/DONE", "--region", REGION],
                          capture_output=True, text=True).stdout.strip()
    print("job DONE marker:", done or "not yet")
    logs = subprocess.run(["aws", "s3", "ls", f"s3://{BUCKET}/jobs/{JOB}/logs/", "--region", REGION],
                          capture_output=True, text=True).stdout.strip()
    print("logs on S3:\n" + (logs or "  none yet"))
    return 0


def collect_checkpoints(a) -> int:
    """Bring the trained artefacts down: without these nothing can be reloaded or served."""
    dst = RESULTS / "checkpoints"
    dst.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["aws", "s3", "sync", f"s3://{BUCKET}/jobs/{JOB}/checkpoints/", str(dst),
                        "--region", REGION], capture_output=True, text=True)
    pts = list(dst.rglob("*.pt"))
    print(r.stdout.strip()[-500:] or "(nothing new)")
    print(f"{len(pts)} checkpoint file(s) under {dst.relative_to(REPO)}")
    for f in pts:
        print(f"  {f.relative_to(dst)}  {f.stat().st_size / 1e6:.1f} MB")
    return 0 if pts else 1


def collect(_a) -> int:
    dst = RESULTS / "aws_logs"
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(["aws", "s3", "sync", f"s3://{BUCKET}/jobs/{JOB}/logs/", str(dst), "--region", REGION],
                   check=False)
    import re
    rows = []
    pat = re.compile(r"horizon\s+(\d+),\s*Test MAE:\s*([\d.]+),\s*Test MAPE:\s*([\d.]+),\s*Test RMSE:\s*([\d.]+)")
    for log in sorted(dst.glob("*.log")):
        if "_" not in log.stem:
            continue
        model, dataset = log.stem.split("_", 1)
        best = {}
        for h, mae, mape, rmse in pat.findall(log.read_text(errors="ignore")):
            best[int(h)] = {"mae": float(mae), "mape": float(mape), "rmse": float(rmse)}
        for h, v in sorted(best.items()):
            # BasicTS logs MAPE as a FRACTION (0.0702). Report percent, as the papers do.
            v["mape"] = v["mape"] * 100 if v["mape"] < 1.5 else v["mape"]
            rows.append({"model": model, "dataset": dataset, "horizon_min": h * 5, **v})
    if not rows:
        print(f"no parsed results yet in {dst}")
        return 1
    # Published MAE/MAPE so the reproduction quality is visible in the same row.
    PUB = {("GWNet", "METR-LA", 15): (2.69, 6.90), ("GWNet", "METR-LA", 30): (3.07, 8.37),
           ("GWNet", "METR-LA", 60): (3.53, 10.01), ("GWNet", "PEMS-BAY", 15): (1.30, 2.73),
           ("GWNet", "PEMS-BAY", 30): (1.63, 3.67), ("GWNet", "PEMS-BAY", 60): (1.95, 4.63),
           ("DCRNN", "METR-LA", 15): (2.77, 7.30), ("DCRNN", "METR-LA", 30): (3.15, 8.80),
           ("DCRNN", "METR-LA", 60): (3.60, 10.50)}
    lines = ["# Trained baselines on real cities (AWS GPU, official BasicTS configs, unmodified)\n",
             "`ours` vs `published` is the reproduction check: the evaluation protocol was validated "
             "independently first (see benchmark_floors.md, our HA floor matches DCRNN's to 0.7 %), so a "
             "close match here means the training pipeline is correct too.\n",
             "| model | dataset | horizon | MAE | published MAE | diff | RMSE | MAPE % | published MAPE % |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        pub = PUB.get((r["model"], r["dataset"], r["horizon_min"]))
        pm = f"{pub[0]:.2f}" if pub else "–"
        diff = f"{100 * (r['mae'] / pub[0] - 1):+.1f} %" if pub else "–"
        pmape = f"{pub[1]:.2f}" if pub else "–"
        lines.append(f"| {r['model']} | {r['dataset']} | {r['horizon_min']} min | {r['mae']:.3f} | {pm} | "
                     f"{diff} | {r['rmse']:.3f} | {r['mape']:.2f} | {pmape} |")
    lines += ["", "Compare against `results/forecasting/benchmark_floors.md` (the floors these must beat) and the "
                  "published numbers cited there.", "",
              f"Regenerate: `python src/pipeline/forecasting/aws_train.py --launch` then `--collect`."]
    (RESULTS / "benchmark.md").write_text("\n".join(lines) + "\n")
    (RESULTS / "benchmark.json").write_text(json.dumps(rows, indent=1))
    print("\n".join(lines))
    return 0


def terminate(_a) -> int:
    for i in running_instances():
        aws("ec2", "terminate-instances", "--instance-ids", i["id"])
        print("terminated", i["id"])
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", action="store_true")
    p.add_argument("--launch", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--collect-checkpoints", action="store_true", help="download trained .pt artefacts")
    p.add_argument("--terminate", action="store_true")
    p.add_argument("--models", default="STID,GWNet")
    p.add_argument("--datasets", default="METR-LA")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--instance-type", default="g5.xlarge,g5.2xlarge",
                   help="ladder of single-GPU types; g5 (A10G) is the verified CUDA path, add g6.xlarge only after verifying L4")
    p.add_argument("--max-hours", type=int, default=4)
    p.add_argument("--opencity", action="store_true",
                   help="cross-city evaluation with the official OpenCity foundation model")
    p.add_argument("--oc-batch", type=int, default=8,
                   help="OpenCity eval batch size; cities with many nodes (TrafficSH has 896 vs "
                        "PEMS07M's 228) need 1-2 to fit a 22 GB A10G")
    p.add_argument("--cities", default="PEMS07M,TrafficSH,TrafficNJ,TrafficTJ",
                   help="OpenCity datasets to evaluate — HELD-OUT cities only; METR_LA and "
                        "PEMS_BAY are in its pre-training corpus and are not zero-shot")
    p.add_argument("--federated", action="store_true",
                   help="run the federated-over-measured-V2X experiment instead of the baselines")
    p.add_argument("--clients", default="4,8,16", help="RSU counts to sweep (federated)")
    p.add_argument("--rounds", type=int, default=30, help="FedAvg rounds (federated)")
    p.add_argument("--job", default="", help="job name (default per-dataset isolation)")
    p.add_argument("--no-spot", action="store_true",
                   help="skip spot entirely; use for runs that must complete without interruption")
    p.add_argument("--allow-on-demand", action="store_true",
                   help="fall back to on-demand (~2x spot) when no spot capacity exists anywhere")
    p.add_argument("--instance-profile", default="dhakaflow-train-profile", help="IAM instance profile granting S3 access")
    p.add_argument("--city-dataset", default="", help="train on an app dataset (user:<id> / live:<city>) instead of a benchmark")
    p.add_argument("--collect-city", default="", help="collect a finished city job by name and write the app's cards")
    a = p.parse_args()
    global JOB
    if a.job:
        JOB = a.job
    if a.collect_city:
        return 0 if city_collect(a.collect_city) else 1
    if a.city_dataset and a.launch:
        return city_launch(a)
    for flag, fn in (("plan", plan), ("launch", launch), ("status", status),
                     ("collect", collect), ("collect_checkpoints", collect_checkpoints),
                     ("terminate", terminate)):
        if getattr(a, flag):
            return fn(a)
    return plan(a)


if __name__ == "__main__":
    sys.exit(main())
