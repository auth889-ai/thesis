"""Cities HTTP endpoints."""
from __future__ import annotations

from app.data.live_providers import observatory as observatory_mod
from app.data.live_providers import google_routes as live_service
from app.routing import trip_analysis as analyze
from app.data import city_corridors
from app.dependencies import _city_bits
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/cities", tags=["city"])
def cities():
    """Every city known to the system, with what each is ALLOWED to claim."""
    reg, catalog = _city_bits()
    cat = catalog()
    return {"cities": [reg.describe(cid, cat) for cid in reg.list_ids()],
            "capability_order": ["LIVE_ONLY", "SIMULATION_ONLY", "ZERO_SHOT",
                                 "FINE_TUNED", "FULL_FORECAST"]}


@router.get("/api/city/{city_id}", tags=["city"])
def city(city_id: str):
    reg, catalog = _city_bits()
    return reg.describe(city_id, catalog())


@router.post("/api/city", tags=["city"])
def create_city(payload: dict):
    """Create a city from a NAME (geocoded via OSM) or a BBOX drawn on the map.

    This is what makes the system city-agnostic in practice rather than in prose: the user names a
    place and the system finds it, instead of an engineer adding a constant.
    """
    reg, catalog = _city_bits()
    name = (payload.get("name") or "").strip()
    bbox = payload.get("bbox")
    if not name:
        return {"error": "name_required"}
    try:
        spec = (reg.create_from_bbox(name, tuple(bbox)) if bbox
                else reg.create_from_name(name))
    except Exception as exc:                       # noqa: BLE001 - surfaced to the user
        return {"error": "create_failed", "detail": f"{type(exc).__name__}: {exc}"}
    return reg.describe(spec.city_id, catalog())


@router.post("/api/city/{city_id}/graph", tags=["city"])
def build_city_graph(city_id: str, payload: dict | None = None):
    """Build the road graph and select STABLE OBSERVATION NODES (major road edges)."""
    reg, catalog = _city_bits()
    try:
        summary = reg.build_graph(city_id, max_nodes=int((payload or {}).get("max_nodes", 250)))
    except Exception as exc:                       # noqa: BLE001
        return {"error": "graph_failed", "detail": f"{type(exc).__name__}: {exc}"}
    return {"city_id": city_id, "graph": summary,
            "capability": reg.describe(city_id, catalog())["forecast_capability"]}


@router.get("/api/city/{city_id}/nodes", tags=["city"])
def city_nodes(city_id: str):
    reg, _ = _city_bits()
    nodes = reg.nodes(city_id)
    return {"city_id": city_id, "count": len(nodes), "nodes": nodes}


@router.get("/api/datasets", tags=["research"])
def datasets():
    """The research datasets, their scale and what each licenses us to claim.

    Arrays stay on Drive/S3 and are never vendored into git; their existence and scale are visible
    here so a reader can see the evidence base rather than infer it.
    """
    _, catalog = _city_bits()
    cat = catalog()
    return {"datasets": cat, "count": len(cat),
            "storage_note": ("arrays live on Google Drive / S3 / HuggingFace and are deliberately "
                             "not committed; this endpoint exposes their existence and scale"),
            "protocol_warning": ("OpenCity metrics use a 288-step horizon on the authors' split; "
                                 "city-specific models use 15-minute DCRNN horizons. Never "
                                 "compare them directly.")}


@router.post("/api/city/{city_id}/observe", tags=["city"])
def city_observe(city_id: str, payload: dict | None = None):
    """Start learning a city: derive its observation corridors from its road graph, sample them
    live every five minutes (persisted), and serve forecasts as soon as the history allows.
    Accepts a registered city id or a free city name (created and geocoded on the spot)."""
    reg, catalog = _city_bits()
    cid = analyze.city_id_for(city_id) or (city_id if reg.get(city_id) else None)
    if cid == "dhaka":
        observatory_mod.observatory.start("dhaka")
        return {"ok": True, "city_id": "dhaka", "corridors": [], "readiness": observatory_mod.observatory.readiness("dhaka")}
    if not cid:
        try:
            cid = reg.create_from_name(city_id).city_id
        except Exception as exc:                       # noqa: BLE001
            return {"ok": False, "error": f"cannot find city {city_id!r}: {type(exc).__name__}: {exc}"}
    try:
        cs = city_corridors.ensure(cid, int((payload or {}).get("corridors", city_corridors.DEFAULT_K)))
        if (payload or {}).get("routes"):
            cs = city_corridors.add_routes(cid, payload["routes"])
    except Exception as exc:                           # noqa: BLE001
        return {"ok": False, "city_id": cid, "error": f"could not derive corridors: {type(exc).__name__}: {exc}"}
    observatory_mod.observatory.start(cid)
    import time as _t
    _t.sleep(2.5)                                       # the wake-up sample is running; let it land
    return {"ok": True, "city_id": cid, "corridors": cs, "readiness": observatory_mod.observatory.readiness(cid),
            "next": {"persistence": "after the first sample", "Chronos-Bolt": "after 8 samples (~40 min)",
                     "OpenCity-plus": "after 288 samples (24 h) with >= 9 corridors"}}


@router.get("/api/city/{city_id}/observe", tags=["city"])
def city_observe_status(city_id: str):
    city_id = analyze.city_id_for(city_id) or city_id
    r = observatory_mod.observatory.readiness(city_id)
    return {"city_id": city_id, "corridors": city_corridors.load(city_id) if city_id != "dhaka" else None,
            "watched": city_id in observatory_mod.observatory.cities(), "readiness": r,
            "live": live_service.service.corridors_for(city_id) if city_corridors.load(city_id) or city_id == "dhaka" else None}
