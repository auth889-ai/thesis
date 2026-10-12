"""The map's forecast layer (core/ml/forecasting/layer/service.py): saved files only, nothing computed from a model on request."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from core.ml.forecasting.layer import service

router = APIRouter()


@router.get("/api/forecast-layer/{city_id}", tags=["forecasting"])
def forecast_layer(city_id: str, at: str | None = None, bbox: str | None = None):
    """`at`: ISO time (default now); `bbox`: west,south,east,north of the map in view (for "best time to leave")."""
    try:
        when = datetime.fromisoformat(at) if at else datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        box = tuple(float(x) for x in bbox.split(",")) if bbox else None
    except ValueError:
        raise HTTPException(400, "at must be an ISO time and bbox four numbers") from None
    if box is not None and len(box) != 4:
        raise HTTPException(400, "bbox needs west,south,east,north")
    return service.layer(city_id, when, box)


def _lab():
    try:
        from core.ml.forecasting.layer import lab
        lab.axis()
        return lab, None
    except (Exception, SystemExit) as exc:                           # noqa: BLE001 - missing libraries or data; said plainly. SystemExit: the research
        return None, f"the Model Lab runs on the research machine only ({type(exc).__name__})"   # loaders exit when a file is missing; inside a request that hung the hosted app (2026-10-10)


@router.get("/api/model-lab/sensors", tags=["forecasting"])
def model_lab_sensors():
    """Sensors, the models with a checkpoint here, and the test period, for the Model Lab page."""
    lab, why = _lab()
    return {"available": False, "reason": why} if lab is None else {"available": True, **lab.sensors()}


@router.post("/api/model-lab/run", tags=["forecasting"])
def model_lab_run(payload: dict):
    """One forecast computed now by RQ1's code: {sensor, at, model} -> recorded, forecast, no change, errors, RQ1 check."""
    lab, why = _lab()
    if lab is None:
        return {"ok": False, "error": why}
    try:
        return lab.run(int(payload.get("sensor", 0)), str(payload.get("at", "")), str(payload.get("model", "D2STGNN")))
    except SystemExit as exc:                                        # a research loader found a file missing: not available, never an exit
        return {"ok": False, "error": f"the Model Lab is missing data on this server ({exc})"}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
