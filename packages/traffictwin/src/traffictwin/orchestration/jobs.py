"""Local, single-flight subprocess jobs for the frozen scientific controller."""
from datetime import datetime, timezone
import json
import fcntl
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid
import secrets

from traffictwin.paths import REPO

ROOT = REPO / "results/v2x/executions"
LOCK = threading.Lock()
PROCESSES = {}
ID = re.compile(r"execution_[0-9]{8}T[0-9]{6}_[a-f0-9]{8}")
ARMS = ("reactive", "persistence_v2x", "predictive_v2x", "oracle_v2x")


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def atomic(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=1))
    temp.replace(path)


def status(job_id):
    if not ID.fullmatch(job_id):
        raise ValueError("invalid job identifier")
    directory = ROOT / job_id
    if not directory.is_dir():
        raise FileNotFoundError(job_id)
    value = read(directory / "status.json")
    request = read(directory / "request.json")
    if (directory / "cancel.request").exists() and value.get("status") in {"queued", "running"}:
        value.update(status="cancelling", stage="cancellation_requested")
    return {"job_id": job_id, **value}


def recent():
    return [status(d.name) for d in sorted(ROOT.glob("execution_*"), reverse=True)[:12] if d.is_dir() and ID.fullmatch(d.name)]


def observation_window():
    from traffictwin.forecasting.training.basicts_train import _prepared
    raw, _ = _prepared("METR-LA")
    return {"minimum": 12, "maximum": int(raw.shape[0]) - 28, "default": int(raw.shape[0]) - 28,
            "history_steps": 12, "interval_s": 300, "dataset": "METR-LA", "origin": "RECORDED_OBSERVATIONS"}


def launch(observation_as_of_index):
    maximum = observation_window()["maximum"]
    if type(observation_as_of_index) is not int or not 12 <= observation_as_of_index <= maximum:
        raise ValueError(f"observation_as_of_index must be an integer from 12 to {maximum}")
    with LOCK:
        ROOT.mkdir(parents=True, exist_ok=True)
        lease = (ROOT / ".controller.lock").open("a+")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise RuntimeError("A frozen-scenario execution is already running.") from None
        # The child inherits the lease, so it remains held across API worker restarts.
        try:
            for previous in recent():
                if previous.get("status") in {"queued", "running", "cancelling"}:
                    atomic(ROOT / previous["job_id"] / "status.json", {
                        **previous, "status": "failed", "stage": "interrupted",
                        "error": "Previous worker exited without a completed result.",
                    })
        except Exception:
            lease.close()
            raise
        job_id = "execution_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_") + uuid.uuid4().hex[:8]
        directory = ROOT / job_id
        directory.mkdir(parents=True, exist_ok=False)
        atomic(directory / "request.json", {"seed": secrets.randbelow(900000) + 1000,
               "observation_as_of_index": observation_as_of_index, "protocol_version": "fresh_identical_state_v2"})
        atomic(directory / "status.json", {"job_id": job_id, "status": "queued", "stage": "starting", "execution_kind": "FRESH_EXECUTION"})
        command = [sys.executable, "-u", str(REPO / "research/closed_loop/interactive.py"), "--job-id", job_id]
        try:
            with (directory / "worker.log").open("w") as log:
                proc = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                        start_new_session=True, pass_fds=(lease.fileno(),))
        except Exception as exc:
            atomic(directory / "status.json", {"job_id": job_id, "status": "failed", "stage": "launch_failed", "error": str(exc)})
            raise
        finally:
            lease.close()
        PROCESSES[job_id] = proc
        def monitor():
            code = proc.wait()
            with LOCK:
                value = read(directory / "status.json")
                if value.get("status") not in ("done", "failed", "cancelled"):
                    atomic(directory / "status.json", {**value, "status": "failed", "stage": "worker_exited", "error": f"worker exited without a completed result (exit {code})"})
        threading.Thread(target=monitor, daemon=True).start()
        return status(job_id)


def cancel(job_id):
    value = status(job_id)
    with LOCK:
        if value.get("status") in {"queued", "running", "cancelling"}:
            (ROOT / job_id / "cancel.request").touch()
            value.update(status="cancelling", stage="cancellation_requested")
    return value


def control(job_id, command):
    status(job_id)
    from .live_controls import enqueue
    return enqueue(ROOT / job_id, command)


def vehicle_trace(job_id, arm, vehicle, after=0):
    status(job_id)
    if arm not in ARMS or after < 0:
        raise ValueError("Invalid trace arm or cursor")
    from traffictwin.data.execution_trace import trace
    return {"run_id": job_id, "arm": arm, "vehicle_id": vehicle, **trace(ROOT / job_id, arm, vehicle, after)}
