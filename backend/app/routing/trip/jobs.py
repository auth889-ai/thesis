"""The background job table: start an analysis in a thread, read its state while it runs."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from . import analysis

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _run(job: str, p: dict) -> None:
    def emit(**kw):
        with _LOCK:
            _JOBS[job].update(kw)
    try:
        city = p.get("city") or "dhaka"
        from app.data import forecast_inputs as dataset_ops
        scope = dataset_ops.scope_for(city)
        if scope:                                       # an uploaded city dataset: the chosen checkpoint runs
            res = dataset_ops.analyze_dataset(p, scope, emit, run_id=job)
        else:
            res = analysis.run(job, p, emit)
        emit(stage="done", step=4, status="done", result=res)
    except (Exception, SystemExit) as exc:          # noqa: BLE001 - the page shows the real reason; a pipeline SystemExit must not leave the job "running" forever
        emit(stage="failed", status="failed", error=f"{type(exc).__name__}: {exc}")


def start(payload: dict) -> str:
    job = "an_" + uuid.uuid4().hex[:8]
    with _LOCK:
        _JOBS[job] = {"job": job, "status": "running", "stage": "Fetching traffic", "step": 0,
                      "started_utc": datetime.now(timezone.utc).isoformat(), "request": payload}
    threading.Thread(target=_run, args=(job, payload), name=job, daemon=True).start()
    return job


def status(job: str) -> dict:
    with _LOCK:
        return dict(_JOBS.get(job) or {"job": job, "status": "unknown"})
