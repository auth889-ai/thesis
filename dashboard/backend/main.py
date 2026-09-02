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
import readers
import schemas

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
