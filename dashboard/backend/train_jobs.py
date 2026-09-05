"""THE TRAINING DISPATCHER — one job id from the Train button to a trusted (or honestly untrusted) model.

    POST /api/train                {dataset, arch, epochs, where?}   -> {job_id}
    GET  /api/train/{job_id}       stage, epoch, curve, metrics, trust, cache_hit, error
    POST /api/train/{job_id}/cancel

Stages: QUEUED -> PREPARING_DATA -> [PROVISIONING_GPU] -> TRAINING -> VALIDATING -> TESTING
        -> VERIFYING_CHECKPOINT -> COMPLETE | FAILED

Execution policy: a job whose estimated CPU time is under LOCAL_BUDGET_S runs here; anything larger
goes to an AWS single-GPU worker (the g5 / A10G path already verified) — unless the request pins
`where`. The GPU never changes a result: same pinned harness, same config, same split, same metrics.

Cache: dataset sha256 + graph sha256 + model + config hash + upstream sha. An identical VALIDATED
checkpoint is reused instead of retraining (stages still run VALIDATING/TESTING from the card).

Every state change is written to results/forecasting/train_jobs/<job>.json, so a server restart
neither loses a job nor leaves a GPU running: unfinished cloud jobs are re-attached on start-up,
and a cancel or a failure terminates the worker.

Data rule: only uploaded / research datasets train or score models. Live corridor history derived
from Google Routes is refused by the pipeline (`basicts_train.load_series`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config

sys.path.insert(0, str(config.REPO))
JOBS_DIR = config.REPO / "results/forecasting/train_jobs"
STAGES = ["QUEUED", "PREPARING_DATA", "PROVISIONING_GPU", "TRAINING", "VALIDATING", "TESTING", "VERIFYING_CHECKPOINT", "COMPLETE", "FAILED"]
LOCAL_BUDGET_S = 120
_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_CANCEL: set[str] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(job: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_DIR / f"{job['job_id']}.json.tmp"
    tmp.write_text(json.dumps(job, indent=1, default=str))
    tmp.replace(JOBS_DIR / f"{job['job_id']}.json")


def _set(job_id: str, **kw) -> dict:
    with _LOCK:
        j = _JOBS[job_id]
        j.update(kw, updated_utc=_now())
        if "stage" in kw and (not j.get("history") or j["history"][-1]["stage"] != kw["stage"]):
            j.setdefault("history", []).append({"stage": kw["stage"], "utc": j["updated_utc"]})
        _save(j)
        return dict(j)


def _fail(job_id: str, why: str) -> None:
    already = get(job_id).get("status") == "failed"
    _set(job_id, stage="FAILED", status="failed", error=why[-1500:] if not already else get(job_id).get("error"))
    j = get(job_id)
    if j.get("cloud_job") and not already:
        try:
            from pipeline.forecasting import aws_train as at
            _aws_environ()
            ids = at.city_terminate(j["cloud_job"])
            _set(job_id, terminated_instances=ids)
        except Exception as exc:                        # noqa: BLE001
            _set(job_id, terminate_error=str(exc)[:300])


def _aws_environ() -> dict | None:
    import predict_lab
    env = predict_lab._aws_env()
    if env:
        os.environ.update({k: env[k] for k in predict_lab.AWS_VARS if k in env})
    return env


# ----------------------------------------------------------------------------- policy
def plan(dataset: str, arch: str, epochs: int, where: str | None) -> dict:
    import predict_lab
    from pipeline.forecasting import basicts_train as bt
    ds = next((d for d in predict_lab.datasets() if d["id"] == dataset), None)
    if not ds:
        raise ValueError(f"unknown dataset {dataset}")
    if not dataset.startswith("user:"):
        raise ValueError("only uploaded / research datasets may train a model (live corridor history is Google-derived)")
    est = bt.estimate_seconds(arch, ds["steps"], ds["nodes"], epochs)
    cloud_ok = predict_lab.cloud()["available"]
    if where in ("cpu", "local"):
        chosen = "local"
    elif where in ("aws", "gpu", "cloud"):
        chosen = "aws" if cloud_ok else "local"
    else:
        chosen = "aws" if est > LOCAL_BUDGET_S and cloud_ok else "local"
    return {"where": chosen, "estimated_local_seconds": round(est), "budget_seconds": LOCAL_BUDGET_S, "cloud_available": cloud_ok,
            "steps": ds["steps"], "nodes": ds["nodes"]}


# ----------------------------------------------------------------------------- the runner
def _run(job_id: str) -> None:
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    j = get(job_id)
    dataset, arch, epochs = j["dataset"], j["arch"], int(j["epochs"])
    try:
        _set(job_id, stage="PREPARING_DATA", status="running")
        prep = bt.prepare(dataset)                        # their data preparation script, locally
        cfg = bt.write_config(arch, prep["name"], prep["nodes"], epochs, prep["steps_per_day"], gpu=False)
        import hashlib
        from pipeline.forecasting.aws_train import BASICTS_SHA
        key = te.cache_key(prep["dataset_hash"], prep["graph_hash"], arch, hashlib.sha256(cfg.read_bytes()).hexdigest()[:8], BASICTS_SHA)
        _set(job_id, cache_key=key, dataset_hash=prep["dataset_hash"], graph_hash=prep["graph_hash"], quality=prep["quality"],
             split="chronological 70/10/20, never shuffled")
        if not prep["quality"]["passed"]:
            _set(job_id, quality_warning="; ".join(prep["quality"]["reasons"]))
        hit = bt.cached(key)
        if hit:
            _set(job_id, cache_hit=True, stage="VALIDATING", trained_on=hit.get("trained_on"))
            card = hit
        else:
            _set(job_id, cache_hit=False)
            if j["where"] == "aws":
                card = _train_aws(job_id, prep, arch, epochs)
            else:
                card = _train_local(job_id, dataset, arch, epochs)
            if card is None:
                return                                    # cancelled or failed; already recorded
        _check_cancel(job_id)
        # VALIDATING: baselines + the trained model on the validation split; selection happens here
        _set(job_id, stage="VALIDATING", best_val_MAE=card.get("best_val_MAE"))
        ev = card.get("evaluation") if hit else None
        if not ev:
            ev = bt.evaluate(card)
        _set(job_id, validation=ev["validation"], selected_by_validation=ev["selected_by_validation"], validation_MAE=ev["validation_MAE"])
        _check_cancel(job_id)
        # TESTING: the untouched last 20 %, reported once
        _set(job_id, stage="TESTING")
        sel = ev["selected_by_validation"]
        _set(job_id, test=ev["test"], test_selected=ev["test"].get(sel), congestion_rule=ev.get("congestion_rule"))
        # VERIFYING_CHECKPOINT: reload and reproduce the reported test error
        _set(job_id, stage="VERIFYING_CHECKPOINT")
        ver = card.get("verification") if hit else None
        if not ver:
            ver = bt.verify_checkpoint(card)
        tr = te.trust(sel, ev["test"].get(sel) or {}, prep["quality"], ver)
        card.update(evaluation=ev, verification=ver, trust=tr)
        bt.save_card(card)
        _set(job_id, stage="COMPLETE", status="done", verification=ver, trust=tr, checkpoint=Path(card["checkpoint"]).name,
             trained_on=card.get("trained_on"), model_name=f"{arch} · trained here", curve=card.get("curve", [])[-2 * epochs:])
    except _Cancelled:
        _fail(job_id, "cancelled by the user")
    except BaseException as exc:                        # noqa: BLE001 — SystemExit from the pipeline is a reason
        _fail(job_id, f"{type(exc).__name__}: {exc}")


class _Cancelled(Exception):
    pass


def _check_cancel(job_id: str) -> None:
    if job_id in _CANCEL:
        raise _Cancelled()


def _train_local(job_id: str, dataset: str, arch: str, epochs: int):
    from pipeline.forecasting import basicts_train as bt
    _set(job_id, stage="TRAINING", epoch=0, epochs=epochs, trained_on="this CPU")

    def progress(**k):
        _check_cancel(job_id)
        _set(job_id, epoch=k["epoch"], curve=k["curve"], last_line=k["line"],
             val_MAE_latest=next((c["value"] for c in reversed(k["curve"]) if c["kind"] == "val_mae"), None))
    return bt.train(dataset, arch, epochs, progress=progress)


def _train_aws(job_id: str, prep: dict, arch: str, epochs: int):
    """Bundle -> S3 -> GPU worker -> pinned harness -> metrics + checkpoint back -> worker terminates."""
    from pipeline.forecasting import aws_train as at
    from pipeline.forecasting import basicts_train as bt
    env = _aws_environ()
    if not env:
        raise RuntimeError("no AWS credentials on the server")
    name = f"{at.city_job_name(get(job_id)['dataset'])}-{arch.lower()}"    # one worker per architecture
    _set(job_id, stage="PROVISIONING_GPU", cloud_job=name, epochs=epochs, epoch=0)
    cmd = [sys.executable, str(config.REPO / "pipeline/forecasting/aws_train.py"), "--launch", "--city-dataset", get(job_id)["dataset"],
           "--models", arch, "--epochs", str(epochs), "--allow-on-demand", "--max-hours", "1", "--job", name]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=config.REPO, env=env, timeout=900)
    if r.returncode != 0:
        raise RuntimeError("could not start the GPU worker: " + (r.stdout + r.stderr)[-700:].strip())
    m = re.search(r"\[launch\] (i-[0-9a-f]+) \(([^)]+)\)", r.stdout)
    _set(job_id, instance=m.group(1) if m else "?", instance_detail=m.group(2) if m else "", trained_on="AWS GPU")
    quiet, t0, training = 0, time.time(), False
    while True:
        time.sleep(15)
        _check_cancel(job_id)
        st = at.city_poll(name)
        log = st["log"] or ""
        curve = bt.parse_curve(log)
        ep = max([c["epoch"] for c in curve], default=0)
        if st["done"]:
            break
        if "=== TRAIN" in log and not training:
            training = True
            _set(job_id, stage="TRAINING")
        if training:
            _set(job_id, epoch=ep, curve=curve[-2 * epochs:], last_line=(log.strip().splitlines() or [""])[-1][-160:],
                 val_MAE_latest=next((c["value"] for c in reversed(curve) if c["kind"] == "val_mae"), None))
        else:
            _set(job_id, provisioning_seconds=int(time.time() - t0), last_line=(log.strip().splitlines() or [""])[-1][-160:])
        if not st["instances"]:
            quiet += 1
            if quiet >= 4:
                raise RuntimeError("the GPU worker is gone without finishing (reclaimed or crashed). Log tail:\n" + log[-700:])
        else:
            quiet = 0
        if time.time() - t0 > 3900:
            raise RuntimeError("gave up after 65 min; the worker's watchdog terminates it")
    if st["done"].strip() != "DONE":
        raise RuntimeError(f"the worker ended with marker {st['done'].strip()!r}. Log tail:\n" + (st["log"] or "")[-700:])
    _set(job_id, stage="TRAINING", last_line="worker finished — collecting the checkpoint")
    cards = at.city_collect(name)
    card = next((c for c in cards if c["arch"] == arch), None)
    if not card:
        raise RuntimeError("the worker finished but no checkpoint came back")
    _set(job_id, curve=card.get("curve", [])[-2 * epochs:], epoch=epochs, instances_after=at.running_instances())
    return card


# ----------------------------------------------------------------------------- API
def start(payload: dict) -> dict:
    dataset, arch = payload.get("dataset", ""), payload.get("arch", "STID")
    epochs = int(payload.get("epochs", 30))
    pl = plan(dataset, arch, epochs, payload.get("where"))
    job_id = "train_" + uuid.uuid4().hex[:10]
    job = {"job_id": job_id, "dataset": dataset, "arch": arch, "epochs": epochs, "where": pl["where"], "plan": pl,
           "stage": "QUEUED", "status": "running", "created_utc": _now(), "updated_utc": _now(), "history": [{"stage": "QUEUED", "utc": _now()}]}
    with _LOCK:
        _JOBS[job_id] = job
        _save(job)
    threading.Thread(target=_run, args=(job_id,), name=job_id, daemon=True).start()
    return {"job_id": job_id, "where": pl["where"], "plan": pl, "poll": f"/api/train/{job_id}"}


def get(job_id: str) -> dict:
    with _LOCK:
        j = _JOBS.get(job_id)
    if j is None:
        f = JOBS_DIR / f"{job_id}.json"
        if f.exists():
            j = json.loads(f.read_text())
            with _LOCK:
                _JOBS[job_id] = j
    return dict(j) if j else {"job_id": job_id, "stage": "UNKNOWN", "status": "unknown"}


def cancel(job_id: str) -> dict:
    j = get(job_id)
    if j.get("status") != "running":
        return {"job_id": job_id, "cancelled": False, "stage": j.get("stage")}
    _CANCEL.add(job_id)
    if j.get("cloud_job"):                               # do not wait for the poll loop: stop billing now
        _fail(job_id, "cancelled by the user")
    return {"job_id": job_id, "cancelled": True, "stage": get(job_id).get("stage")}


def list_jobs(limit: int = 20) -> list[dict]:
    files = sorted(JOBS_DIR.glob("train_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit] if JOBS_DIR.exists() else []
    out = []
    for f in files:
        try:
            j = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        out.append({k: j.get(k) for k in ("job_id", "dataset", "arch", "epochs", "where", "stage", "status", "cache_hit", "created_utc", "trust")})
    return out


def reattach_on_startup() -> None:
    """Jobs left running by a previous server process: cloud jobs are re-polled; local ones cannot
    be resumed (the trainer process died with the server) and are marked FAILED — and any GPU
    worker of a failed job is terminated."""
    for f in JOBS_DIR.glob("train_*.json") if JOBS_DIR.exists() else []:
        try:
            j = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if j.get("status") != "running":
            continue
        with _LOCK:
            _JOBS[j["job_id"]] = j
        if j.get("cloud_job") and j.get("stage") in ("PROVISIONING_GPU", "TRAINING"):
            threading.Thread(target=_resume_aws, args=(j["job_id"],), name=j["job_id"], daemon=True).start()
        else:
            _fail(j["job_id"], "the server restarted while this job was running")


def _resume_aws(job_id: str) -> None:
    """Continue polling a cloud job after a restart; on DONE, collect and finish like a fresh run."""
    from pipeline.forecasting import aws_train as at
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    j = get(job_id)
    try:
        _aws_environ()
        name, arch, epochs = j["cloud_job"], j["arch"], int(j["epochs"])
        quiet = 0
        while True:
            st = at.city_poll(name)
            if st["done"]:
                break
            if not st["instances"]:
                quiet += 1
                if quiet >= 3:
                    raise RuntimeError("the GPU worker is gone without finishing")
            _set(job_id, epoch=max([c["epoch"] for c in bt.parse_curve(st["log"] or "")], default=0))
            time.sleep(15)
        cards = at.city_collect(name)
        card = next((c for c in cards if c["arch"] == arch), None)
        if not card:
            raise RuntimeError("no checkpoint came back")
        prep = {"quality": j.get("quality") or card.get("quality") or {}}
        _set(job_id, stage="VALIDATING"); ev = bt.evaluate(card)
        _set(job_id, stage="TESTING", validation=ev["validation"], test=ev["test"], selected_by_validation=ev["selected_by_validation"])
        _set(job_id, stage="VERIFYING_CHECKPOINT"); ver = bt.verify_checkpoint(card)
        sel = ev["selected_by_validation"]
        tr = te.trust(sel, ev["test"].get(sel) or {}, prep["quality"], ver)
        card.update(evaluation=ev, verification=ver, trust=tr); bt.save_card(card)
        _set(job_id, stage="COMPLETE", status="done", verification=ver, trust=tr, test_selected=ev["test"].get(sel))
    except BaseException as exc:                        # noqa: BLE001
        _fail(job_id, f"{type(exc).__name__}: {exc}")
