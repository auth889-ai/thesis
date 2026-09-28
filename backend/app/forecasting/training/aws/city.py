"""A city-dataset job: the official baselines trained on an app dataset (user:/live:) on a GPU —
same harness, same derived config, same metrics as the CPU path in basicts_train.py, just faster
and for more epochs. The app launches, polls and collects these."""
from __future__ import annotations

import json
import re
import subprocess
import time

from .ec2 import run_instance, running_instances, s3, terminate_instances
from .scripts import CITY_SCRIPT, render
from .settings import AMI, BASICTS_SHA, BUCKET, REGION, RESULTS


def city_job_name(dataset_id: str) -> str:
    return "city-" + re.sub(r"[^a-z0-9]+", "-", dataset_id.lower()).strip("-")


def city_launch(a) -> int:
    from app.forecasting.training import basicts_train as bt
    job = a.job or city_job_name(a.city_dataset)
    if running_instances(job):
        print(f"refusing: a {job} instance is already running — use --status, or --terminate first")
        return 2
    prep = bt.prepare(a.city_dataset)                    # their prep script, locally
    name = prep["name"]
    models = [m for m in a.models.split(",") if m]
    cfgs = {m: bt.write_config(m, name, prep["nodes"], a.epochs, prep["steps_per_day"], gpu=True) for m in models}
    for m in models:                                      # the CPU-flavoured config the app loads the checkpoint with
        bt.write_config(m, name, prep["nodes"], a.epochs, prep["steps_per_day"], gpu=False)
    base = f"s3://{BUCKET}/jobs/{job}"
    s3("rm", f"{base}/", "--recursive", check=False)
    s3("sync", str(bt.BTS / "datasets" / name), f"{base}/in/datasets/")
    for m, c in cfgs.items():
        s3("cp", str(c), f"{base}/in/configs/{m}.py")
    manifest = {"job": job, "dataset": a.city_dataset, "dataset_sha256": prep.get("dataset_hash"), "graph_sha256": prep.get("graph_hash"),
                "models": models, "epochs": a.epochs, "upstream": "GestaltCogTeam/BasicTS", "upstream_sha": BASICTS_SHA,
                "split": "chronological 70/10/20 (their TRAIN_VAL_TEST_RATIO)", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    mf = RESULTS / "aws_city_jobs" / f"{job}.manifest.json"
    mf.parent.mkdir(parents=True, exist_ok=True); mf.write_text(json.dumps(manifest, indent=1))
    s3("cp", str(mf), f"{base}/in/manifest.json")
    print(f"[upload] {name}: {prep['desc']['num_time_steps']} steps x {prep['nodes']} nodes + {len(cfgs)} config(s) -> {base}/in/")
    script = render(CITY_SCRIPT, NAME=job, BUCKET=BUCKET, SHA=BASICTS_SHA, MODELS=" ".join(models), DSNAME=name, MAXH=str(a.max_hours))
    iid, chosen, _ = run_instance(a, script, job)
    if not iid:
        return 4
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) — trains {models} for {a.epochs} epochs, uploads, terminates.")
    entry = {"job": job, "instance": iid, "type": chosen[0], "market": chosen[2], "region": REGION, "ami": AMI,
             "models": a.models, "datasets": a.city_dataset, "epochs": a.epochs,
             "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s3": f"{base}/"}
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "aws_jobs.jsonl", "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    (RESULTS / "aws_city_jobs" / f"{job}.json").write_text(json.dumps({**entry, "prep": prep, "configs": {m: str(c) for m, c in cfgs.items()}}, indent=1))
    return 0


def city_terminate(job: str) -> list[str]:
    """Stop every instance of this job now (a cancelled or failed job must not keep billing)."""
    return terminate_instances(job)


def city_poll(job: str) -> dict:
    """What the app shows while a city job runs: instance state, DONE marker, the live log tail."""
    inst = running_instances(job)
    done = subprocess.run(["aws", "s3", "cp", f"s3://{BUCKET}/jobs/{job}/DONE", "-", "--region", REGION], capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["aws", "s3", "cp", f"s3://{BUCKET}/jobs/{job}/logs/live.log", "-", "--region", REGION], capture_output=True, text=True).stdout
    return {"instances": inst, "done": done, "log": log}


def city_collect(job: str) -> list[dict]:
    """Bring their checkpoints + metrics down and write the app's cards, one per architecture."""
    from app.forecasting.training import basicts_train as bt
    meta = json.loads((RESULTS / "aws_city_jobs" / f"{job}.json").read_text())
    prep = meta["prep"]; name = prep["name"]
    dst = RESULTS / "checkpoints_cloud" / job
    dst.mkdir(parents=True, exist_ok=True)
    s3("sync", f"s3://{BUCKET}/jobs/{job}/checkpoints/", str(dst))
    logs = RESULTS / "aws_logs" / job
    logs.mkdir(parents=True, exist_ok=True)
    s3("sync", f"s3://{BUCKET}/jobs/{job}/logs/", str(logs), check=False)
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
        card = bt.make_card(meta["datasets"], arch, int(meta["epochs"]), prep, cfg, runs[-1], log_text, where=f"AWS {meta['type']} GPU ({meta['market']})")
        cards.append(card)
        print(f"[collect] {arch}: test {json.dumps(card['test_metrics'].get('overall'))} vs persistence {json.dumps(card['persistence_test'])}")
    return cards
