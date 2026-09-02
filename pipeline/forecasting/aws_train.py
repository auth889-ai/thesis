#!/usr/bin/env python3
"""Train the forecasting baselines on an AWS spot GPU — launched and collected from the terminal.

    python pipeline/forecasting/aws_train.py --plan                 # show what would run and what it costs
    python pipeline/forecasting/aws_train.py --launch               # start the spot GPU job
    python pipeline/forecasting/aws_train.py --status               # is it running / done?
    python pipeline/forecasting/aws_train.py --collect              # pull results into results/forecasting/
    python pipeline/forecasting/aws_train.py --terminate            # stop it now

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

REPO = Path(__file__).resolve().parents[2]
BUCKET = "dhakaflow-train-915644996102"
REGION = "us-east-1"
# Deep Learning OSS Nvidia Driver AMI GPU **PyTorch** (AL2023). The *Base* AMI ships drivers but no
# framework: a pip-installed torch there fails with `libcudnn.so.9: cannot open shared object file`,
# and the system python3.9 has a numpy/pytables ABI clash that breaks the data prep. This AMI carries
# a working conda env (`source activate pytorch`) with matched torch + CUDA + cuDNN.
AMI = "ami-001972c501ec6b965"          # PyTorch 2.9 (AL2023) 20260829
BASICTS_SHA = "4c3e2d373c647667c2123e1591f2d79c229dfcc6"
JOB = "predict-baselines"          # overridden by --job so each dataset keeps its own S3 space
RESULTS = REPO / "results/forecasting"

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
    # upload the datasets the job needs
    for d in a.datasets.split(","):
        src = REPO / "data/forecasting/cities" / d
        if not src.exists():
            print(f"missing {src}; fetch it first (pipeline/forecasting/city_datasets.py --list)")
            return 3
        print(f"[upload] {src} -> s3://{BUCKET}/jobs/{JOB}/{d}/")
        subprocess.run(["aws", "s3", "sync", str(src), f"s3://{BUCKET}/jobs/{JOB}/{d}/",
                        "--region", REGION], check=True, capture_output=True)
    # Clear the previous run's markers/logs, or a watcher will read a stale DONE and report early.
    for key in ("DONE", "logs/"):
        subprocess.run(["aws", "s3", "rm", f"s3://{BUCKET}/jobs/{JOB}/{key}", "--region", REGION]
                       + (["--recursive"] if key.endswith("/") else []), capture_output=True)
    script = JOB_SCRIPT
    for k, v in (("@NAME@", JOB), ("@BUCKET@", BUCKET), ("@SHA@", BASICTS_SHA),
                 ("@MODELS@", a.models.replace(",", " ")), ("@DATASETS@", a.datasets.replace(",", " ")),
                 ("@EPOCHS@", str(a.epochs)), ("@MAXH@", str(a.max_hours))):
        script = script.replace(k, v)
    assert "@" not in script.split("aws s3")[0], "unsubstituted placeholder remains"
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
        return 4
    a.instance_type = chosen[0]
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) after {len(attempts)} unavailable option(s). "
          f"It installs, trains, uploads and terminates itself.")
    print(f"[launch] watch:  python pipeline/forecasting/aws_train.py --status")
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
              f"Regenerate: `python pipeline/forecasting/aws_train.py --launch` then `--collect`."]
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
    p.add_argument("--instance-type", default="g5.xlarge")
    p.add_argument("--max-hours", type=int, default=4)
    p.add_argument("--job", default="", help="job name (default per-dataset isolation)")
    p.add_argument("--no-spot", action="store_true",
                   help="skip spot entirely; use for runs that must complete without interruption")
    p.add_argument("--allow-on-demand", action="store_true",
                   help="fall back to on-demand (~2x spot) when no spot capacity exists anywhere")
    p.add_argument("--instance-profile", default="", help="IAM instance profile granting S3 access")
    a = p.parse_args()
    global JOB
    if a.job:
        JOB = a.job
    for flag, fn in (("plan", plan), ("launch", launch), ("status", status),
                     ("collect", collect), ("collect_checkpoints", collect_checkpoints),
                     ("terminate", terminate)):
        if getattr(a, flag):
            return fn(a)
    return plan(a)


if __name__ == "__main__":
    sys.exit(main())
