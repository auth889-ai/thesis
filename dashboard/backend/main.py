"""DhakaFlow dashboard — FastAPI application.

    cd dashboard/backend && python main.py        # http://127.0.0.1:8000
                                                  # OpenAPI at /api/docs

Four files, because the backend has one job: read the evidence this project produced and serve it.

    config.py    where every evidence file lives and the command that regenerates it
    schemas.py   the response contract (Pydantic v2) — what each endpoint promises
    readers.py   one function per panel: open the file, shape it, attach provenance
    main.py      routes and the SSE stream

Every response carries `provenance` (source file, regenerating command, reality label). A panel
with no evidence returns `available: false` and the command to produce it, so the interface can
never show an invented number.

Real-time uses Server-Sent Events, not WebSocket: this dashboard is display-only, so a
bidirectional socket buys nothing. SSE is plain HTTP, the browser's EventSource reconnects on its
own, and the stream sends a diff-sized payload only when something changed.

Open source used, with thanks: FastAPI (MIT), Uvicorn (BSD-3), Pydantic (MIT); in the browser
MapLibre GL JS (BSD-3), Chart.js (MIT), OpenStreetMap tiles (ODbL).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
import corridors as corridor_registry
import observatory as observatory_mod
import live as live_service
import predict_live
import readers
import schemas
import credentials as key_store
import simulate

app = FastAPI(title="DhakaFlow", version="1.0.0", docs_url="/api/docs",
              description="Live Dhaka traffic, forecasting, routing and V2X evidence.")


@app.get("/api/traffic", response_model=schemas.TrafficResponse, tags=["traffic"])
def traffic():
    """Live corridor congestion, with recorder freshness."""
    return readers.traffic()


@app.get("/api/forecast", response_model=schemas.ForecastResponse, tags=["forecast"])
def forecast():
    """Trained models, the published comparison and checkpoint verification."""
    return readers.forecast()


@app.get("/api/routing", response_model=schemas.RoutingResponse, tags=["routing"])
def routing():
    """Routing arms on paired seeds and the ACT / NO_ACTION decision."""
    return readers.routing()


@app.get("/api/simulation", response_model=schemas.SimulationResponse, tags=["simulation"])
def simulation():
    """SUMO before / after and the network-wide decision guard."""
    return readers.simulation()


@app.get("/api/network", response_model=schemas.NetworkResponse, tags=["network"])
def network():
    """V2X delivery ratio, latency and loss from the MOSAIC sweep."""
    return readers.network()


@app.get("/api/evidence", response_model=schemas.EvidenceResponse, tags=["evidence"])
def evidence():
    """The phase gate and the evidence index."""
    return readers.evidence()


# ---------------------------------------------------------------------------
# LIVE DHAKA MODE
#
# These endpoints call the Google Routes API from the SERVER. The browser never sees a key and
# never talks to Google directly. Every response carries source / retrieved_at / is_live /
# request_status, and a failed call is reported as unavailable — recorded data is never
# substituted behind a "live" label.
# ---------------------------------------------------------------------------

@app.get("/api/live/corridors", tags=["live"])
def live_corridors(force: bool = False):
    """Every monitored Dhaka corridor, live. `force=true` bypasses the short in-memory cache."""
    return live_service.service.corridors(force=force)


@app.get("/api/live/corridor/{corridor_id}", tags=["live"])
def live_corridor(corridor_id: str, force: bool = False):
    """One corridor: traffic-aware ETA, static ETA, penalty, geometry and speed intervals."""
    return live_service.service.corridor(corridor_id, force=force)


@app.get("/api/live/routes", tags=["live"])
def live_routes(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    """Alternative routes between two points, traffic-aware, from the live API."""
    return live_service.service.routes((origin_lat, origin_lng), (dest_lat, dest_lng))


@app.get("/api/live/health", tags=["live"])
def live_health():
    """API health and credential presence. Reports a key fingerprint, never a key."""
    return {"live": live_service.service.health(), "credentials": key_store.status()}


@app.get("/api/predict/{corridor_id}", tags=["predict"])
def predict(corridor_id: str, force: bool = False):
    """Live state, then 5 / 15 / 30 / 60 min ahead.

    The response separates LIVE DHAKA INPUT from MODEL VALIDATED ON REAL BENCHMARK DATA and sets
    `dhaka_accuracy_claimed: false` — there is not yet enough lawful Dhaka ground truth to state
    an accuracy figure, so none is given.
    """
    cur = live_service.service.corridor(corridor_id, force=force)
    pred = predict_live.predictor.predict(
        corridor_id,
        current_state=cur.get("category", "UNKNOWN"),
        duration_s=cur.get("duration_s"),
        static_s=cur.get("static_duration_s"))
    return {"live": cur, "prediction": pred,
            "source": "google_routes + this project's recorded verdicts",
            "retrieved_at": cur.get("retrieved_at"),
            "is_live": cur.get("is_live", False),
            "request_status": cur.get("request_status", "UNKNOWN")}


@app.post("/api/simulate", tags=["simulate"])
def simulate_start(payload: dict):
    """Start a SUMO counterfactual from the selected live state. Returns a job to poll.

    Results are a SIMULATED COUNTERFACTUAL on the calibrated twin, never a live-road outcome.
    """
    return simulate.runner.start(
        corridor_id=payload.get("corridor_id", ""),
        category=payload.get("category", "UNKNOWN"),
        seeds=payload.get("seeds") or [11, 12, 13],
        horizon=int(payload.get("horizon", 1800)),
        compliance=float(payload.get("compliance", 0.3)))


@app.get("/api/simulate/{job_id}", tags=["simulate"])
def simulate_status(job_id: str):
    return simulate.runner.status(job_id)


@app.get("/api/corridors", tags=["live"])
def corridor_list():
    """The monitored corridors and which of them a counterfactual can honestly be run on."""
    return {"corridors": [corridor_registry.describe(c) for c in corridor_registry.CORRIDORS],
            "total": len(corridor_registry.CORRIDORS),
            "sumo_mapped": sum(1 for c in corridor_registry.CORRIDORS if c["sumo_mapped"])}


# ---------------------------------------------------------------------------
# CITY LAYER — any city, created at runtime. No city is hard-coded here.
# ---------------------------------------------------------------------------

def _city_bits():
    """Imported lazily so the dashboard still starts if the research deps are absent."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.city.datasets import catalog
    from pipeline.city.registry import registry
    return registry, catalog


@app.get("/api/cities", tags=["city"])
def cities():
    """Every city known to the system, with what each is ALLOWED to claim."""
    reg, catalog = _city_bits()
    cat = catalog()
    return {"cities": [reg.describe(cid, cat) for cid in reg.list_ids()],
            "capability_order": ["LIVE_ONLY", "SIMULATION_ONLY", "ZERO_SHOT",
                                 "FINE_TUNED", "FULL_FORECAST"]}


@app.get("/api/city/{city_id}", tags=["city"])
def city(city_id: str):
    reg, catalog = _city_bits()
    return reg.describe(city_id, catalog())


@app.post("/api/city", tags=["city"])
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


@app.post("/api/city/{city_id}/graph", tags=["city"])
def build_city_graph(city_id: str, payload: dict | None = None):
    """Build the road graph and select STABLE OBSERVATION NODES (major road edges)."""
    reg, catalog = _city_bits()
    try:
        summary = reg.build_graph(city_id, max_nodes=int((payload or {}).get("max_nodes", 250)))
    except Exception as exc:                       # noqa: BLE001
        return {"error": "graph_failed", "detail": f"{type(exc).__name__}: {exc}"}
    return {"city_id": city_id, "graph": summary,
            "capability": reg.describe(city_id, catalog())["forecast_capability"]}


@app.get("/api/city/{city_id}/nodes", tags=["city"])
def city_nodes(city_id: str):
    reg, _ = _city_bits()
    nodes = reg.nodes(city_id)
    return {"city_id": city_id, "count": len(nodes), "nodes": nodes}


@app.get("/api/datasets", tags=["research"])
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


@app.get("/api/models", tags=["research"])
def models(city_id: str = "dhaka"):
    """Every forecasting model and whether it can honestly serve this city right now."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting.adapters.registry import available_for
    cd = observatory_mod.observatory.city_data(city_id)
    return {"city_id": city_id, "input": cd.describe(),
            "models": available_for(cd)}


# ---------------------------------------------------------------------------
# OBSERVATORY — the rolling window lives in the SERVER, not in a CLI invocation
# ---------------------------------------------------------------------------

@app.get("/api/observatory", tags=["live"])
def observatory_status(city_id: str = "dhaka"):
    return {"status": observatory_mod.observatory.status(),
            "readiness": observatory_mod.observatory.readiness(city_id)}


@app.post("/api/observatory/start", tags=["live"])
def observatory_start(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.start(cid)


@app.post("/api/observatory/sample", tags=["live"])
def observatory_sample(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.sample(cid)


@app.get("/api/forecast/{city_id}", tags=["predict"])
def city_forecast(city_id: str, horizons: str = "5,15,30,60"):
    """The real forecast path: whichever model can honestly serve this city, or a LABELLED baseline.

    Replaces the four-class empirical transition model as the main prediction. The response always
    carries the model used, whether it was a baseline, and why every other model refused.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting.adapters.registry import forecast as run_forecast
    hs = [int(h) for h in horizons.split(",") if h.strip().isdigit()]
    cd = observatory_mod.observatory.city_data(city_id)
    out = run_forecast(cd, hs)
    out["input"] = cd.describe()
    out["readiness"] = observatory_mod.observatory.readiness(city_id)
    return out


@app.get("/api/health", tags=["meta"])
def health():
    """Liveness plus data freshness — a dashboard must say when its data is stale."""
    h = readers.recorder_health()
    return {"status": "ok", "recorder_healthy": h.healthy, "last_tick_utc": h.last_tick_utc,
            "age_minutes": h.age_minutes}


def _pulse() -> dict:
    """A diff-sized payload: the browser already holds the tables, so only freshness and the
    latest level per corridor travel on the wire."""
    t, e = readers.traffic(), readers.evidence()
    return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "recorder": t.recorder.model_dump() if t.recorder else None,
            "corridors": [{"id": c.id, "level": c.level, "state": c.state} for c in t.corridors],
            "bins": t.bins, "span_hours": t.span_hours, "gate_passed": e.gate_passed}


@app.get("/api/stream", tags=["realtime"])
async def stream(request: Request):
    """SSE. Emits on change, heartbeats otherwise, and tells the client how long to back off."""
    async def events():
        yield f"retry: {config.SSE_INTERVAL_S * 1000}\n\n"
        last = None
        while not await request.is_disconnected():
            payload = json.dumps(_pulse(), default=str)
            if payload != last:
                yield f"event: update\ndata: {payload}\n\n"
                last = payload
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(config.SSE_INTERVAL_S)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.on_event("startup")
def _start_observatory() -> None:
    """Begin accumulating the rolling window as soon as the server is up.

    The buffer only means anything if it is filling, and the audit's finding was that it never
    could. Starting it here is what makes readiness a real countdown: leave the server running and
    the 288-step window fills in about a day. Sampling is off by default in tests, where a live
    API call per tick would be both slow and pointless.
    """
    import os
    if os.environ.get("DHAKAFLOW_NO_OBSERVATORY"):
        return
    try:
        observatory_mod.observatory.start("dhaka")
    except Exception:                              # noqa: BLE001 - never block startup
        pass


FRONTEND = config.REPO / "dashboard/frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    if (config.REPO / "docs/media").exists():
        app.mount("/media", StaticFiles(directory=config.REPO / "docs/media"), name="media")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("DhakaFlow -> http://127.0.0.1:8000    docs -> /api/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
