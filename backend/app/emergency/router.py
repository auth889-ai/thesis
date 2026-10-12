"""Ambulance alert endpoints. Everything they start or return is a simulation on the city's twin; nothing is sent
to a person or a service."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.safety import reach, sos

from core.simulation.ambulance import results, service
from app.emergency.schemas import RunRequest
from core.common.paths import REPO
from core.simulation.twin.live import runtime as live_sim_mod

router = APIRouter()


@router.post("/api/emergency/runs", tags=["emergency"])
def start_run(req: RunRequest):
    """Start a simulated ambulance run on the live twin (one run at a time)."""
    try:
        params = service.live_request(req.city_id, req.arm, req.technology, req.equipped_share, req.demand, req.depart_s)
    except service.Refused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    out = live_sim_mod.live_sim.start({**params, "duration_s": req.duration_s, "step_delay_ms": req.step_delay_ms})
    return {**out, "label": "SIMULATED"}


@router.get("/api/emergency/runs/{run_id}", tags=["emergency"])
def get_run(run_id: str):
    """The ambulance part of a live run: the one running now, or a finished one from the twin's history."""
    state = live_sim_mod.live_sim.state(with_vehicles=False)
    if state.get("run_id") == run_id and state.get("emergency"):
        return {"run_id": run_id, "status": state.get("status"), "sim_time_s": state.get("sim_time_s"), "city_id": (state.get("params") or {}).get("network"), "emergency": state["emergency"]}
    for rec in live_sim_mod.live_sim.history():
        if rec.get("run_id") == run_id and (rec.get("params") or {}).get("emergency"):
            return {"run_id": run_id, "status": "done", "sim_time_s": rec.get("sim_time_s"), "city_id": rec["params"].get("network"), "emergency": rec.get("emergency") or {"label": "SIMULATED", **rec["params"]["emergency"]}}
    raise HTTPException(status_code=404, detail="no ambulance run with this id")


@router.get("/api/emergency/results/{city_id}", tags=["emergency"])
def get_results(city_id: str):
    """The result tables of the ambulance experiments for one city, one per demand; never another city's."""
    return {"city_id": city_id, "label": "SIMULATED", "tables": [results.read(city_id, d) for d in service.DEMANDS if d != "dhaka_density"],   # the corridor's runs are RQ2b's, on the RQ2 card
            "technologies": {t: {"usable": not missing, "unsourced": missing} for t, missing in service.model.usable().items() if t not in ("ideal", "none")}}


@router.get("/api/emergency/reach/{city_id}", tags=["emergency"])
def get_reach(city_id: str, points: bool = True):
    """How far an ambulance reaches from the city's hospitals (the built file: map speeds, and the recorded variant where the city
    has recorded sites); never computed on the request, never another city's."""
    return reach.read(city_id, with_points=points)


@router.get("/api/emergency/reach/{city_id}/nearest", tags=["emergency"])
def get_nearest(city_id: str, lat: float, lon: float, k: int = 3):
    """The hospitals nearest a point by drive time at map speeds, from the city's own routing server."""
    return reach.nearest(city_id, lat, lon, k=max(1, min(k, 10)))


_ISO: dict[tuple, dict] = {}


@router.get("/api/emergency/reach/{city_id}/isochrone", tags=["emergency"])
def get_isochrone(city_id: str, lat: float, lon: float):
    """The 10/20/30-minute polygons around a point at map speeds, from the city's own routing server; kept while the app runs."""
    from core.simulation.routing import valhalla
    key = (city_id, round(lat, 5), round(lon, 5))
    if key not in _ISO:
        got = valhalla.isochrone(city_id, lat, lon)
        if not got["available"]:
            return got
        _ISO[key] = got
    return _ISO[key]


def _iso_cached(city_id: str, lat: float, lon: float):
    key = (city_id, round(lat, 5), round(lon, 5))
    if key in _ISO:
        return _ISO[key], True
    from core.simulation.routing import valhalla
    got = valhalla.isochrone(city_id, lat, lon)
    if got.get("available"):
        _ISO[key] = got
    return got, False


@router.get("/api/emergency/reach/{city_id}/live", tags=["emergency"])
def get_live_reach(city_id: str, lat: float, lon: float, k: int = 3):
    """Live reach from a tapped point (step K): the nearest hospitals and their 10/20/30-minute polygons, computed now by the city's
    routing server and timed; the thesis's saved shares come with it, unchanged. Isochrones are kept per hospital while the app runs."""
    return reach.live(city_id, lat, lon, k=max(1, min(k, 5)), iso=_iso_cached)


@router.get("/api/emergency/sos/results", tags=["emergency"])
def sos_results():
    """The synthetic motion traces (labelled SYNTHETIC) and what the detection rule did with each; the rule and its source."""
    return sos.read()


@router.get("/api/emergency/sos/trace/{kind}", tags=["emergency"])
def sos_trace(kind: str):
    """One trace for the browser to replay through the same rule: a synthetic kind, or `sumo_collision`, built by the live collision run from SUMO's own record."""
    got = sos.trace(kind)
    if not got:
        raise HTTPException(404, f"no trace '{kind}'" + (": run `make run-sos-collide` first" if kind == sos.COLLISION_KIND else ""))
    return got


@router.get("/api/emergency/sos/path/{city_id}", tags=["emergency"])
def sos_path(city_id: str, online: bool = True, peak_g: float | None = None):
    """The alert path of a TEST SOS in this city, step by step; every number from a file or the city's config."""
    return sos.path_steps(city_id, online, peak_g)


@router.post("/api/emergency/sos/test", tags=["emergency"])
def sos_test(payload: dict):
    """A TEST SOS raised on a device: kept in memory for the alerts feed of this machine only. Never sent, never dialled."""
    return sos.raise_test(str(payload.get("city_id") or "dhaka"), payload.get("peak_g"), bool(payload.get("online", True)), str(payload.get("source") or "sensor"))


# ------------------------------------------------------------------ RQ2 (docs/PAPER_MAP.md): read-only, nothing computed on request
RQ2_DIR = REPO / "results/emergency/dhaka/rq2"           # core.simulation.ambulance.study.RQ2; not imported here (it loads pandas, which the hosted app lacks)


@router.get("/api/emergency/rq2", tags=["emergency"])
def rq2_summary():
    import json as _json
    p = RQ2_DIR / "summary.json"
    if not p.exists():
        return {"available": False, "note": "RQ2 has not been run yet: research/ambulance_rq2/README.md"}
    return {"available": True, **_json.loads(p.read_text())}


@router.get("/api/emergency/rq2/figures/{name}", tags=["emergency"])
def rq2_figure(name: str):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    p = (RQ2_DIR / "figures" / name).resolve()
    if p.parent != (RQ2_DIR / "figures").resolve() or p.suffix != ".png" or not p.exists():
        raise HTTPException(404, "no such figure")
    return FileResponse(p, media_type="image/png")
