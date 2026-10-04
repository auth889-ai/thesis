"""A LargeST job: PatchSTG trained on one region with the authors' own code, on a GPU.

    python -m app.forecasting.training.aws_train --largest GLA --launch --instance-type g5.2xlarge --max-hours 8
    python -m app.forecasting.training.aws_train --largest GLA --status
    python -m app.forecasting.training.aws_train --largest GLA --collect

Spot only (on-demand needs --no-spot, after its cost is approved); tagged project=dhakaflow, phase=patchstg. After
every epoch the instance uploads the resumable state, the best weights and the log to `jobs/<job>/state/`, so a spot
interruption loses less than one epoch: the same --launch command continues from that state (--fresh discards it).
A watchdog on the instance stops the job and writes `FAILED.json` when the log is silent for 30 minutes or memory
runs out; --status and --collect copy that record into aws_jobs.jsonl and flag a log that stopped updating.

The instance clones LMissher/PatchSTG at the pinned SHA, receives the region's flow array and the adjacency
our released-weights test built with their `construct_adj` (so train and test patch the same way), and trains
through `patchstg_official --mode train`: the authors' `Solver` with the dictionary their argparse builds from
`config/<REGION>.conf`, `train()` then `test()` of the best epoch. Their `main.py` itself cannot run on a rented
single-GPU box for three reasons found by launching it: its first parser rejects every option but `--config`
(`unrecognized arguments: --num_workers 4`), so its 32 loader workers are fixed and were killed for memory on GLA
with 16 GB; and the GBA/GLA/CA configs name GPU 7/4/6 of the authors' machine (`invalid device ordinal`). SD, whose
config says GPU 0 and whose data is small, did train with `python main.py --config ./config/SD.conf` as released.
The switch passes their own `num_workers` option as 4 and falls back to GPU 0 when the named one is absent.

Collect brings the log and the trained weights down, parses the per-step and average lines the authors'
`metric` prints, and records the row beside the released-weights row in patchstg_largest.{json,md}.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from pathlib import Path

from app.forecasting.training import patchstg_official as po

from .ec2 import run_instance, running_instances, s3
from .largest_script import SCRIPT
from .scripts import WATCHDOG, render
from .settings import AMI, BUCKET, REGION, RESULTS, REPO

PATCHSTG_SHA = "8b298b230227a304a082e05241c69dca3740a73d"       # upstream/UPSTREAM_PINS.yaml: PatchSTG

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
    for key in ("DONE", "FAILED.json") + (("state/", "logs/") if a.fresh else ()):     # an interrupted job's state and logs stay
        s3("rm", f"{base}/{key}", *(["--recursive"] if key.endswith("/") else []), check=False)
    resumed = s3("ls", f"{base}/state/{region.lower()}_state.pt", check=False).stdout.strip()
    print(f"[state] {'continuing from the per-epoch state on S3: ' + resumed if resumed else 'no saved state: starts at epoch 1'}")
    print(f"[upload] {flow.name} ({flow.stat().st_size / 1e6:.0f} MB) -> {base}/in/")
    s3("cp", str(flow.resolve()), f"{base}/in/{flow.name}")
    if adj.exists():
        s3("cp", str(adj), f"{base}/in/adj.npy")
        print(f"[upload] adj.npy (built by their construct_adj during the released-weights test) -> {base}/in/")
    for f in ("patchstg_official.py", "patchstg_resume.py"):
        s3("cp", str(Path(po.__file__).with_name(f)), f"{base}/in/{f}")
    script = render(SCRIPT.replace("@WATCHDOG@", WATCHDOG.strip()), NAME=job, BUCKET=BUCKET, SHA=PATCHSTG_SHA, REGION=region, LREGION=region.lower(),
                    EPOCHS=str(a.epochs if a.epochs_set else 0), MAXH=str(a.max_hours))
    iid, chosen, attempts = run_instance(a, script, job)
    if not iid:
        return 4
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) after {len(attempts)} unavailable option(s); trains with the authors' Solver, uploads, terminates")
    entry = {"job": job, "instance": iid, "type": chosen[0], "region": REGION, "ami": AMI, "models": "PatchSTG", "datasets": f"LargeST-{region}",
             "epochs": a.epochs if a.epochs_set else "authors' config", "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s3": base + "/",
             "market": chosen[2], "phase": a.phase, "resumed_from_state": bool(resumed)}
    _ledger(entry)
    return 0


def _ledger(entry: dict) -> None:
    path = RESULTS / "aws_jobs.jsonl"
    if path.exists() and json.dumps(entry) in path.read_text():
        return
    with open(path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def record_failure(job: str) -> dict | None:
    """Copy the instance's FAILED.json (written by its watchdog) into the job ledger, once."""
    r = s3("cp", f"s3://{BUCKET}/jobs/{job}/FAILED.json", "-", check=False)
    if r.returncode or not r.stdout.strip():
        return None
    failed = json.loads(r.stdout)
    _ledger(failed)
    return failed


def stale_minutes(listing: str, now: float | None = None) -> float | None:
    """Minutes since the `aws s3 ls` line's timestamp (local time, as the CLI prints it)."""
    m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", listing.strip())
    return None if not m else ((now or time.time()) - time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))) / 60


def largest_status(a) -> int:
    job = a.job or job_name(a.largest.upper())
    base = f"s3://{BUCKET}/jobs/{job}"
    inst = running_instances(job)
    print("instances:", inst or "none running")
    failed = record_failure(job)
    print("FAILED:", failed["reason"] if failed else "no failure record")
    print("DONE:", s3("ls", f"{base}/DONE", check=False).stdout.strip() or "not yet")
    print("state:", s3("ls", f"{base}/state/", check=False).stdout.strip() or "no epoch finished yet")
    age = stale_minutes(s3("ls", f"{base}/logs/live.log", check=False).stdout)
    if inst and age is not None and age > 30:
        print(f"WARNING: the log last reached S3 {age:.0f} minutes ago while an instance is running. If the on-box watchdog is "
              f"stalled too, stop it: aws ec2 terminate-instances --region {REGION} --instance-ids {' '.join(i['id'] for i in inst)}")
    return 0


_STEP = re.compile(r"^step (\d+), mae: ([\d.]+), rmse: ([\d.]+), mape: ([\d.]+)", re.M)
_AVG = re.compile(r"^average, mae: ([\d.]+), rmse: ([\d.]+), mape: ([\d.]+)", re.M)
_BEST = re.compile(r"Best epoch is: (\d+)")
_RESUME = re.compile(r"^\[resume\] ", re.M)


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
    record_failure(job)
    logs = RESULTS / "patchstg_logs"
    parts = logs / f"{job}_parts"
    parts.mkdir(parents=True, exist_ok=True)
    s3("sync", f"{base}/logs/", str(parts), "--exclude", "*", "--include", f"PatchSTG_{region}*.log", "--include", "memory_*.log", check=False)
    pieces = sorted(parts.glob(f"PatchSTG_{region}*.log"), key=lambda f: f.stat().st_mtime)      # one per instance, oldest first
    if not pieces:
        print(f"no training log on S3 yet for {job} (DONE: {s3('ls', f'{base}/DONE', check=False).stdout.strip() or 'not yet'})")
        return 1
    (logs / f"{region}_train_aws.log").write_text("".join(f.read_text(errors="ignore") for f in pieces))
    ck = RESULTS / "checkpoints" / "PatchSTG" / region
    ck.mkdir(parents=True, exist_ok=True)
    s3("cp", f"{base}/checkpoints/PatchSTG/{region}/{region.lower()}_model", str(ck / f"{region.lower()}_model"), check=False)
    text = (logs / f"{region}_train_aws.log").read_text(errors="ignore")
    parsed = parse_official_log(text)
    if not parsed:
        print("the log has no test block yet (still training, or the cap hit before the test)")
        return 1
    pub = po.PUBLISHED[region]
    rec = {"region": region, "mode": "train", "nodes": po.REGIONS[region], "device": "cuda (AWS g4dn.xlarge)", "seconds": None,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "epochs": a.epochs if a.epochs_set else "authors' config",
           "best_epoch": parsed["best_epoch"], "weights": "trained here with the authors' recipe", "average": parsed["average"],
           "published": {"mae": pub[0], "rmse": pub[1], "mape_pct": pub[2]}, "steps": parsed["steps"], "job": job,
           "instances": len(pieces), "resumes": len(_RESUME.findall(text)),
           "upstream": "LMissher/PatchSTG (MIT), " + ("Solver through patchstg_official, 4 loader workers, one epoch per train() call" if f"{region} train: MAE" in text else "main.py run as released")}
    rec["mae_gap_pct"] = round((rec["average"]["mae"] - pub[0]) / pub[0] * 100, 2)
    po.write(rec)
    ev = REPO / "evidence/patchstg" / region                        # the log and the hashes behind the row
    ev.mkdir(parents=True, exist_ok=True)
    with gzip.open(ev / "train.log.gz", "wb") as fh:
        fh.write(text.encode())
    sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()      # noqa: E731
    weights = ck / f"{region.lower()}_model"
    (ev / "record.json").write_text(json.dumps({**{k: rec[k] for k in ("region", "job", "weights", "upstream", "epochs", "best_epoch", "instances", "resumes", "average", "published", "mae_gap_pct", "generated_utc")},
        "log": "train.log.gz", "log_sha256": hashlib.sha256(text.encode()).hexdigest(), "checkpoint": str(weights.relative_to(REPO)), "checkpoint_sha256": sha(weights) if weights.exists() else None,
        "ledger": [json.loads(l) for l in (RESULTS / "aws_jobs.jsonl").read_text().splitlines() if json.loads(l).get("job") == job]}, indent=1))
    print(f"{region} trained: MAE {rec['average']['mae']} RMSE {rec['average']['rmse']} MAPE {rec['average']['mape_pct']} % "
          f"(published {pub[0]} / {pub[1]} / {pub[2]} %, gap {rec['mae_gap_pct']:+.2f} %); weights in {ck}")
    return 0
