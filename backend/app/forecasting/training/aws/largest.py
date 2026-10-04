"""A LargeST job: PatchSTG trained on one region with the authors' own `main.py`, on a GPU.

    python -m app.forecasting.training.aws_train --largest SD --launch --no-spot --max-hours 6
    python -m app.forecasting.training.aws_train --largest SD --collect

The instance clones LMissher/PatchSTG at the pinned SHA, receives the region's flow array and the adjacency
our released-weights test built with their `construct_adj` (so train and test patch the same way), and runs
the authors' entrypoint exactly as their README says — `python main.py --config ./config/<REGION>.conf` —
which trains for `max_epoch` and then tests the best epoch. Their first parser accepts `--config` alone and
rejects anything else (the first SD job died on `unrecognized arguments: --num_workers 4`), so nothing else is
passed; a shorter run is asked for through a copy of their config with `max_epoch` changed, never an option.

Collect brings the log and the trained weights down, parses the per-step and average lines the authors'
`metric` prints, and records the row beside the released-weights row in patchstg_largest.{json,md}.
"""
from __future__ import annotations

import json
import re
import time

from app.forecasting.training import patchstg_official as po

from .ec2 import run_instance, running_instances, s3
from .scripts import render
from .settings import AMI, BUCKET, REGION, RESULTS

PATCHSTG_SHA = "8b298b230227a304a082e05241c69dca3740a73d"       # upstream/UPSTREAM_PINS.yaml: PatchSTG

SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@; SHA=@SHA@; RG=@REGION@; LRG=@LREGION@; EPOCHS=@EPOCHS@
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &          # hard watchdog
( while true; do sleep 30; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/live.log >/dev/null 2>&1; done ) &
aws s3 cp s3://$BUCKET/jobs/$NAME/in/ /home/ec2-user/in/ --recursive || true
cd /home/ec2-user
git clone -q https://github.com/LMissher/PatchSTG.git patchstg && cd patchstg && git checkout -q $SHA
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /opt/conda/bin/python \
         /usr/local/bin/python3 /usr/bin/python3 $(ls -d /opt/*/bin/python /opt/*/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
[ -z "$PY" ] && { echo NO_TORCH; aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/; echo FAILED > /tmp/DONE; aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE; shutdown -h now; }
$PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
$PY -m pip install -q timm scikit-learn pandas
mkdir -p data/$RG cpt log && cp /home/ec2-user/in/flow$LRG.npz data/$RG/ && cp /home/ec2-user/in/adj.npy data/$RG/ 2>/dev/null || true
CONF=./config/$RG.conf
[ "$EPOCHS" != "0" ] && { sed "s/^max_epoch = .*/max_epoch = $EPOCHS/" ./config/$RG.conf > ./config/${RG}_short.conf; CONF=./config/${RG}_short.conf; }
echo "=== TRAIN PatchSTG $RG (authors' main.py) ==="
timeout $((@MAXH@ * 3600 - 1800)) $PY main.py --config $CONF 2>&1 | tee /tmp/PatchSTG_$RG.log
aws s3 cp /tmp/PatchSTG_$RG.log s3://$BUCKET/jobs/$NAME/logs/ || true
aws s3 cp log/${LRG}_log s3://$BUCKET/jobs/$NAME/logs/${LRG}_log || true
aws s3 cp cpt/${LRG}_model s3://$BUCKET/jobs/$NAME/checkpoints/PatchSTG/$RG/${LRG}_model || true
aws s3 cp /var/log/dhakaflow.log s3://$BUCKET/jobs/$NAME/logs/ || true
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE s3://$BUCKET/jobs/$NAME/DONE
shutdown -h now
"""


def job_name(region: str) -> str:
    return f"patchstg-{region.lower()}"


def largest_launch(a) -> int:
    region = a.largest.upper()
    if region not in po.REGIONS:
        print(f"region must be one of {sorted(po.REGIONS)}")
        return 3
    job = a.job or job_name(region)
    if running_instances(job):
        print(f"refusing: a {job} instance is already running — use --status, or --terminate first")
        return 2
    missing = po.link_release(region)                     # the same links the released-weights test made
    flow = po.REPO / "data" / region / f"flow{region.lower()}.npz"
    adj = po.REPO / "data" / region / "adj.npy"
    if not flow.exists():
        print(f"missing {flow}: " + ", ".join(missing))
        return 3
    base = f"s3://{BUCKET}/jobs/{job}"
    for key in ("DONE", "logs/"):
        s3("rm", f"{base}/{key}", *(["--recursive"] if key.endswith("/") else []), check=False)
    print(f"[upload] {flow.name} ({flow.stat().st_size / 1e6:.0f} MB) -> {base}/in/")
    s3("cp", str(flow.resolve()), f"{base}/in/{flow.name}")
    if adj.exists():
        s3("cp", str(adj), f"{base}/in/adj.npy")
        print(f"[upload] adj.npy (built by their construct_adj during the released-weights test) -> {base}/in/")
    script = render(SCRIPT, NAME=job, BUCKET=BUCKET, SHA=PATCHSTG_SHA, REGION=region, LREGION=region.lower(),
                    EPOCHS=str(a.epochs if a.epochs_set else 0), MAXH=str(a.max_hours))
    iid, chosen, attempts = run_instance(a, script, job)
    if not iid:
        return 4
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) after {len(attempts)} unavailable option(s); trains with the authors' main.py, uploads, terminates")
    entry = {"job": job, "instance": iid, "type": chosen[0], "region": REGION, "ami": AMI, "models": "PatchSTG", "datasets": f"LargeST-{region}",
             "epochs": a.epochs if a.epochs_set else "authors' config", "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s3": base + "/"}
    with open(RESULTS / "aws_jobs.jsonl", "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return 0


_STEP = re.compile(r"^step (\d+), mae: ([\d.]+), rmse: ([\d.]+), mape: ([\d.]+)", re.M)
_AVG = re.compile(r"^average, mae: ([\d.]+), rmse: ([\d.]+), mape: ([\d.]+)", re.M)
_BEST = re.compile(r"Best epoch is: (\d+)")


def parse_official_log(text: str) -> dict | None:
    """The test block the authors' `main.py` prints after training: per-step rows and the 12-step average."""
    steps = [{"step": int(s), "mae": float(m), "rmse": float(r), "mape_pct": round(float(p) * 100, 4)} for s, m, r, p in _STEP.findall(text)]
    avg = _AVG.findall(text)
    if not steps or not avg:
        return None
    m, r, p = avg[-1]
    best = _BEST.findall(text)
    return {"steps": steps[-12:], "average": {"mae": float(m), "rmse": float(r), "mape_pct": round(float(p) * 100, 4)},
            "best_epoch": int(best[-1]) if best else None}


def largest_collect(a) -> int:
    region = a.largest.upper()
    job = a.job or job_name(region)
    base = f"s3://{BUCKET}/jobs/{job}"
    logs = RESULTS / "patchstg_logs"
    logs.mkdir(parents=True, exist_ok=True)
    r = s3("cp", f"{base}/logs/PatchSTG_{region}.log", str(logs / f"{region}_train_aws.log"), check=False)
    if r.returncode:
        print(f"no training log on S3 yet for {job} (DONE: {s3('ls', f'{base}/DONE', check=False).stdout.strip() or 'not yet'})")
        return 1
    ck = RESULTS / "checkpoints" / "PatchSTG" / region
    ck.mkdir(parents=True, exist_ok=True)
    s3("cp", f"{base}/checkpoints/PatchSTG/{region}/{region.lower()}_model", str(ck / f"{region.lower()}_model"), check=False)
    parsed = parse_official_log((logs / f"{region}_train_aws.log").read_text(errors="ignore"))
    if not parsed:
        print("the log has no test block yet (still training, or the cap hit before the test)")
        return 1
    pub = po.PUBLISHED[region]
    rec = {"region": region, "mode": "train", "nodes": po.REGIONS[region], "device": "cuda (AWS g4dn.xlarge)", "seconds": None,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "epochs": a.epochs if a.epochs_set else "authors' config",
           "best_epoch": parsed["best_epoch"], "weights": "trained here with the authors' recipe", "average": parsed["average"],
           "published": {"mae": pub[0], "rmse": pub[1], "mape_pct": pub[2]}, "steps": parsed["steps"], "job": job,
           "upstream": "LMissher/PatchSTG (MIT), main.py run as released"}
    rec["mae_gap_pct"] = round((rec["average"]["mae"] - pub[0]) / pub[0] * 100, 2)
    po.write(rec)
    print(f"{region} trained: MAE {rec['average']['mae']} RMSE {rec['average']['rmse']} MAPE {rec['average']['mape_pct']} % "
          f"(published {pub[0]} / {pub[1]} / {pub[2]} %, gap {rec['mae_gap_pct']:+.2f} %); weights in {ck}")
    return 0
