"""The benchmark job (METR-LA / PEMS-BAY with the official configs), plus the federated and
OpenCity variants that share its launch path: plan, launch, status, collect, terminate."""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.paths import REPO

from .ec2 import aws, run_instance, running_instances, s3
from .report import parse_logs, write_benchmark
from .scripts import FED_SCRIPT, JOB_SCRIPT, OPENCITY_SCRIPT, render
from .settings import AMI, BASICTS_SHA, BUCKET, OPENCITY_SHA, REGION, RESULTS


def plan(a, job: str) -> int:
    models, datasets = a.models.split(","), a.datasets.split(",")
    print(f"job              {job}")
    print(f"instance         {a.instance_type} spot, {REGION}, AMI {AMI}")
    print(f"models           {models}")
    print(f"datasets         {datasets}")
    print(f"epochs           {a.epochs} (official configs otherwise unmodified)")
    print(f"runs             {len(models) * len(datasets)}")
    print(f"max hours        {a.max_hours} (hard watchdog, then terminate)")
    print(f"est. spot cost   ~${0.5 * a.max_hours:.2f} at ~$0.50/h for g5.xlarge (verify in billing)")
    print(f"results          s3://{BUCKET}/jobs/{job}/  ->  results/forecasting/ via --collect")
    inst = running_instances(job)
    print(f"already running  {inst if inst else 'no'}")
    return 0


def _upload_inputs(a, job: str) -> int:
    """The datasets the job needs (OpenCity pulls its own from the authors' HuggingFace), and the extras of each variant."""
    base = f"s3://{BUCKET}/jobs/{job}"
    for d in ([] if a.opencity else a.datasets.split(",")):
        src = REPO / "data/forecasting/cities" / d
        if not src.exists():
            print(f"missing {src}; fetch it first (city_datasets.py --list)")
            return 3
        print(f"[upload] {src} -> {base}/{d}/")
        s3("sync", str(src), f"{base}/{d}/")
    if "STDMAE" in a.models.split(","):
        masks = Path.home() / ".dhakaflow/upstream/STD-MAE_mask_save"
        pts = sorted(masks.glob("*.pt")) if masks.exists() else []
        if not pts:
            print(f"missing the authors' mask checkpoints in {masks} (Jimmy-7664/STD-MAE/mask_save)")
            return 3
        for f in pts:
            s3("cp", str(f), f"{base}/mask_save/{f.name}")
        print(f"[upload] {len(pts)} STD-MAE mask checkpoint(s) -> {base}/mask_save/")
    for key in ("DONE", "logs/"):                      # a watcher must not read a stale DONE and report early
        s3("rm", f"{base}/{key}", *(["--recursive"] if key.endswith("/") else []), check=False)
    if a.opencity:
        boot = REPO / "backend/app/forecasting/opencity/_opencity_boot.py"
        s3("cp", str(boot), f"{base}/{boot.name}")
        print(f"[upload] OpenCity compatibility bootstrap -> {base}/")
    if a.federated:
        extra = [REPO / "backend/app/forecasting/federated/federated_forecast.py"] + sorted((REPO / "results/networking").glob("penetration_p*_s*.json"))
        for f in extra:
            s3("cp", str(f), f"{base}/{f.name}")
        npz = REPO / "data/forecasting/cities/metr_la.npz"
        if npz.exists():
            s3("cp", str(npz), f"{base}/metr_la.npz")
        print(f"[upload] federated inputs: code + {len(extra) - 1} simulated-V2X profile files")
    return 0


def launch(a, job: str) -> int:
    if running_instances(job):
        print(f"refusing: a {job} instance is already running — use --status, or --terminate first")
        return 2
    rc = _upload_inputs(a, job)
    if rc:
        return rc
    template = OPENCITY_SCRIPT if a.opencity else (FED_SCRIPT if a.federated else JOB_SCRIPT)
    script = render(template, NAME=job, BUCKET=BUCKET, SHA=BASICTS_SHA, MODELS=a.models.replace(",", " "), DATASETS=a.datasets.replace(",", " "),
                    EPOCHS=str(a.epochs), MAXH=str(a.max_hours), CLIENTS=a.clients.replace(",", " "), ROUNDS=str(a.rounds),
                    OCSHA=OPENCITY_SHA, OCDATASETS=a.cities.replace(",", " "), OCBATCH=str(a.oc_batch))
    iid, chosen, attempts = run_instance(a, script, job)
    if not iid:
        return 4
    a.instance_type = chosen[0]
    print(f"[launch] {iid} ({chosen[0]} {chosen[2]} in {chosen[1]}) after {len(attempts)} unavailable option(s). It installs, trains, uploads and terminates itself.")
    print("[launch] watch:  python -m app.forecasting.training.aws_train --status")
    # A history, so each dataset's run keeps ITS OWN hardware provenance; a single overwritten file
    # once stamped the METR-LA results with the PEMS-BAY instance id.
    RESULTS.mkdir(parents=True, exist_ok=True)
    entry = {"job": job, "instance": iid, "type": a.instance_type, "region": REGION, "ami": AMI, "models": a.models, "datasets": a.datasets, "epochs": a.epochs,
             "launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s3": f"s3://{BUCKET}/jobs/{job}/"}
    with open(RESULTS / "aws_jobs.jsonl", "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    (RESULTS / "aws_job.json").write_text(json.dumps(entry, indent=1))
    return 0


def status(_a, job: str) -> int:
    inst = running_instances(job)
    print("instances:", inst if inst else "none running")
    done = s3("ls", f"s3://{BUCKET}/jobs/{job}/DONE", check=False).stdout.strip()
    print("job DONE marker:", done or "not yet")
    logs = s3("ls", f"s3://{BUCKET}/jobs/{job}/logs/", check=False).stdout.strip()
    print("logs on S3:\n" + (logs or "  none yet"))
    return 0


def collect_checkpoints(_a, job: str) -> int:
    """Bring the trained artefacts down: without these nothing can be reloaded or served."""
    dst = RESULTS / "checkpoints"
    dst.mkdir(parents=True, exist_ok=True)
    r = s3("sync", f"s3://{BUCKET}/jobs/{job}/checkpoints/", str(dst), check=False)
    pts = list(dst.rglob("*.pt"))
    print(r.stdout.strip()[-500:] or "(nothing new)")
    print(f"{len(pts)} checkpoint file(s) under {dst.relative_to(REPO)}")
    for f in pts:
        print(f"  {f.relative_to(dst)}  {f.stat().st_size / 1e6:.1f} MB")
    return 0 if pts else 1


def collect(_a, job: str) -> int:
    dst = RESULTS / "aws_logs"
    dst.mkdir(parents=True, exist_ok=True)
    s3("sync", f"s3://{BUCKET}/jobs/{job}/logs/", str(dst), check=False)
    rows = parse_logs(dst)
    if not rows:
        print(f"no parsed results yet in {dst}")
        return 1
    print(write_benchmark(rows))
    return 0


def terminate(_a, job: str) -> int:
    for i in running_instances(job):
        aws("ec2", "terminate-instances", "--instance-ids", i["id"])
        print("terminated", i["id"])
    return 0


def finish(a, job: str) -> int:
    """One command after a job's DONE marker: the log becomes a leaderboard row, the checkpoint comes down and
    is scored under Protocol B on the persisted test and validation blocks, and the conformal layer is re-run.
    Every step is the same command a reviewer would run by hand; this only runs them in order."""
    import subprocess
    import sys
    rc = collect(a, job)
    if rc:
        return rc
    collect_checkpoints(a, job)
    py = [sys.executable, "-m", "app.forecasting.evaluation.evaluate_models"]
    for ds in a.datasets.split(","):
        ds = ds.strip()
        if not ds:
            continue
        # every persisted block of this dataset (each roads-count and test block that Protocol B has run) gets the new model
        import re
        blocks = sorted(RESULTS.glob(f"protocol_b/{ds}_*_w*_n*_s*.npz"))
        if not blocks:
            print(f"[finish] no persisted Protocol B block for {ds}; run evaluate_models once with --region val and --region test first")
        seen = set()
        for block in blocks:
            m = re.match(rf"{re.escape(ds)}_(val|test)_w(\d+)_n(\d+)_s(\d+)\.npz", block.name)
            if not m:
                continue
            region, windows, nodes, seed = m.group(1), m.group(2), m.group(3), m.group(4)
            full = len(__import__("app.forecasting.evaluation.evaluate_models", fromlist=["load"]).load(ds)[0])
            max_nodes = "0" if int(nodes) >= full else nodes
            staged = RESULTS / "protocol_b" / f"_stage_{block.stem}_checkpoints.npz"
            subprocess.run(py + ["--stage", "checkpoints", "--dataset", ds, "--windows", windows, "--seed", seed, "--max-nodes", max_nodes,
                                 "--region", region, "--stage-out", str(staged)], check=True, cwd=REPO)
            subprocess.run(py + ["--dataset", ds, "--windows", windows, "--seed", seed, "--max-nodes", max_nodes, "--region", region, "--merge", str(staged)],
                           check=True, cwd=REPO)
            staged.unlink(missing_ok=True)
            seen.add((windows, nodes, seed))
        for windows, nodes, seed in sorted(seen):
            subprocess.run([sys.executable, "-m", "app.forecasting.evaluation.conformal", "--dataset", ds, "--windows", windows, "--nodes", nodes, "--seed", seed], check=True, cwd=REPO)
    print(f"[finish] {job}: leaderboard, checkpoints, Protocol B and conformal rows updated")
    return 0
