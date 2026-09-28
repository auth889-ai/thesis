"""Research HTTP endpoints."""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/research/status", tags=["research"])
def research_status():
    """Computed research gates and the evidence files that produced them.

    This is the canonical project status used by SYSTEM and documentation. It never converts a
    missing/negative result into a presentational success state.
    """
    from app.protocols.research_status import compute_research_status
    return compute_research_status()


@router.get("/api/research/executions", tags=["research"])
def scientific_executions():
    from app.control import jobs as scientific_jobs
    from app.control.scenario import REFERENCE, read
    from app import evidence_paths as config
    from app.forecasting.operations.road_forecasts import _background
    result = {"jobs": scientific_jobs.recent(),
              "arms": list(scientific_jobs.ARMS), "reference_run": REFERENCE}
    try:
        protocol = read(config.REPO / "results/v2x/closed_loop" / REFERENCE / "PROTOCOL.json")
        result.update(available=True, observation_window=scientific_jobs.observation_window(), network=_background(protocol["city_id"]),
                      scenario={k: protocol[k] for k in ("city_id", "profile", "profile_params", "penetration",
                                                         "fork_t0_s", "simulation_duration_s")})
    except (OSError, KeyError, ValueError) as exc:
        result.update(available=False, error=f"Frozen scenario unavailable: {exc}")
    return result


@router.post("/api/research/executions", status_code=202, tags=["research"])
def scientific_execution_start(payload: dict):
    from app.control import jobs as scientific_jobs
    if set(payload) != {"observation_as_of_index"}:
        raise HTTPException(422, "Select an observation window. Seeds are internal provenance; all controllers run together.")
    try:
        return scientific_jobs.launch(payload["observation_as_of_index"])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@router.get("/api/research/executions/{job_id}", tags=["research"])
def scientific_execution_status(job_id: str):
    from app.control import jobs as scientific_jobs
    try:
        return scientific_jobs.status(job_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc))


@router.post("/api/research/executions/{job_id}/cancel", tags=["research"])
def scientific_execution_cancel(job_id: str):
    from app.control import jobs as scientific_jobs
    try:
        return scientific_jobs.cancel(job_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc))


@router.post("/api/research/executions/{job_id}/controls", status_code=202, tags=["research"])
def scientific_execution_control(job_id: str, payload: dict):
    from app.control import jobs
    try:
        return jobs.control(job_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@router.get("/api/research/executions/{job_id}/trace", tags=["research"])
def scientific_execution_trace(job_id: str, arm: str = "predictive_v2x", vehicle: str = "", after: int = 0):
    from app.control import jobs
    try:
        return jobs.vehicle_trace(job_id, arm, vehicle, after)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc))
