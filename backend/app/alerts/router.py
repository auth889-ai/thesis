"""Road watches and onset alerts over HTTP."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.alerts import service

router = APIRouter()


class Watch(BaseModel):
    person_id: str = Field(min_length=1, max_length=64)
    dataset: str = Field(min_length=1, max_length=64)
    node: str = Field(min_length=1, max_length=32)
    label: str | None = Field(default=None, max_length=200)


@router.get("/api/protocol-b/onset-now", tags=["predict"])
def onset_now(dataset: str = "METR_LA", as_of: int = 20000, model: str | None = None):
    """Roads about to tip at this dataset moment, from the served model's fresh forecast against the train-split threshold."""
    from core.ml.forecasting.operations import onset_now as on
    try:
        return on.onsets(dataset, as_of, model)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


@router.post("/api/watch/roads", tags=["alerts"])
def post_watch(w: Watch):
    return service.watch(w.person_id, w.dataset, w.node, w.label)


@router.get("/api/watch/roads", tags=["alerts"])
def get_watches(person_id: str):
    return {"watches": service.watches(person_id), "alerts": service.alerts(person_id)}


@router.delete("/api/watch/roads/{watch_id}", tags=["alerts"])
def delete_watch(watch_id: str, person_id: str):
    if not service.unwatch(person_id, watch_id):
        raise HTTPException(404, "no such watch for this person")
    return {"deleted": watch_id}


@router.post("/api/watch/roads/evaluate", tags=["alerts"])
def evaluate(dataset: str = "METR_LA", as_of: int = 20000, model: str | None = None):
    """Evaluate every watch on the dataset at a moment: an alert when onset is predicted at two consecutive moments, once per episode."""
    try:
        return service.evaluate(dataset, as_of, model)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


@router.get("/api/alerts/feed", tags=["alerts"])
def alerts_feed(city_id: str, person_id: str | None = None):
    """Every alert for one city in one list, each stamped with its origin (real, recorded data, simulated or test).
    An ambulance appears while a simulated one drives on the city's twin; a mesh line states what the city's saved offline
    mesh result (PONS, simulated) would deliver; SOS alerts are named and empty until that demo exists."""
    return service.feed(city_id, person_id)

