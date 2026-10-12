"""Live simulations started from the map (core/simulation/live_jobs): computed now by the thesis's code, labelled SIMULATION."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.simulation.live_jobs.runner import RUNNER

router = APIRouter()


@router.post("/api/live/{kind}", tags=["simulation"])
def start(kind: str, payload: dict | None = None):
    """Start one live simulation (v2x, sos, mesh, signals) with its parameters; one runs at a time for the whole site."""
    r = RUNNER.start(kind, payload or {})
    if not r["started"]:
        raise HTTPException(409 if "already running" in r["reason"] or "one at a time" in r["reason"] else 400, r["reason"])
    return r


@router.get("/api/live/jobs/{job_id}", tags=["simulation"])
def frames(job_id: str, since: int = 0):
    """The job's frames from `since`, its status and, at the end, the measured result with the thesis check."""
    job = RUNNER.get(job_id)
    if not job:
        raise HTTPException(404, "no such simulation")
    return job.view(since)


@router.post("/api/live/jobs/{job_id}/stop", tags=["simulation"])
def stop(job_id: str):
    return RUNNER.stop(job_id)
