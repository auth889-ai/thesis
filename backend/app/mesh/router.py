"""Offline mesh endpoints: the saved, simulated result table of a city. Nothing runs here and nothing is sent to anyone."""
from __future__ import annotations

from fastapi import APIRouter

from core.networking.mesh import results

router = APIRouter()


@router.get("/api/mesh/results/{city_id}", tags=["mesh"])
def get_results(city_id: str):
    """The city's offline mesh table (PONS, store-carry-forward), or "no data for this city"."""
    return {"city_id": city_id, "label": results.LABEL, "table": results.read(city_id)}


@router.get("/api/mesh/replay/{city_id}", tags=["mesh"])
def get_replay(city_id: str):
    """The mesh study's phones on the map, second by second, and which were within radio range (core/networking/mesh/map_replay.py),
    with the study's plain result; or "no data for this city"."""
    import json
    import re

    from core.common.paths import REPO
    if not re.fullmatch(r"[a-z0-9_]+", city_id):
        return {"city_id": city_id, "available": False, "reason": "no data for this city"}
    f = REPO / "results/networking/mesh" / city_id / "map_replay.json"
    s = REPO / "results/networking/mesh" / city_id / "summary.json"
    if not f.exists() or not s.exists():
        return {"city_id": city_id, "available": False, "reason": "no data for this city"}
    return {"available": True, "plain": json.loads(s.read_text()).get("plain"), **json.loads(f.read_text())}
