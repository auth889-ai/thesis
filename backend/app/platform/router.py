"""System HTTP endpoints."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from core.common import evidence_paths as config
from core.simulation.closed_loop.protocols.evidence import panel_readers as readers
from core.common import credentials as key_store
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/tiles/{city_id}/basemap.pmtiles", tags=["meta"])
def own_tiles(city_id: str, request: Request):
    """Our own PMTiles basemap for the city (Planetiler from the OpenStreetMap extract, kept in the routing bucket): the browser's Range
    forwarded to S3. A city without a file answers 404 with the reason."""
    from fastapi.responses import Response
    from app.platform import tiles
    status, body, headers = tiles.read_range(city_id, request.headers.get("range"))
    return Response(content=body, status_code=status, headers=headers)


@router.get("/api/networking/prefetch", tags=["meta"])
def prefetch_results():
    """The weak-signal experiment (emulated network, synthetic signal profiles; energy estimated from Bartendr), or "no data"."""
    from core.networking.prefetch import results as pr
    return pr.read()


@router.get("/api/tiles/{city_id}/info", tags=["meta"])
def own_tiles_info(city_id: str):
    """Whether the city has an own basemap for the trip pack, and its size."""
    from app.platform import tiles
    return tiles.info(city_id)


@router.get("/api/config/map", tags=["meta"])
def map_config():
    """Which base map the browser should use. Without a Mapbox public token it is OpenFreeMap's OpenStreetMap vector
    style (no key, no account). Also the worldwide buildings source and the satellite picture the twin can show. Never a
    secret key."""
    from app.platform import basemap_source
    from core.simulation.twin import buildings_source
    extra = {"buildings": buildings_source.source(),    # worldwide 3D buildings; see that module for licence and attribution
             "satellite": basemap_source.SATELLITE}
    tok = key_store.mapbox_token()
    if tok:
        return {"provider": "mapbox",
                "tiles": f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{{z}}/{{x}}/{{y}}?access_token={tok}",
                "attribution": "© Mapbox © OpenStreetMap", **extra}
    return {**basemap_source.STREETS, **extra}


@router.get("/api/networking/conditions", tags=["network"])
def networking_conditions():
    """Measured V2X delivery per (latency, loss), beside the federated forecast error.

    Both halves are read from evidence files. The delivery table comes from the Eclipse MOSAIC
    ITS-G5 sweep; the forecast errors come from the federated runs on AWS. They are SIMULATED
    communication events, not radio-hardware measurements, and the payload says so.
    """
    import csv as _csv
    lat = config.REPO / "results/networking/latency.csv"
    fed = config.REPO / "results/forecasting/federated.json"
    conditions = []
    if lat.exists():
        for r in _csv.DictReader(lat.open()):
            conditions.append({
                "added_latency_ms": int(r["added_latency_ms"]),
                "loss_pct": int(float(r["loss_pct"])),
                "delivery_single": float(r["frac_delivered_single_shot"]),
                "delivery_repeat": float(r["frac_delivered_1hz_repeat"]),
                "effective_latency_ms": float(r["effective_latency_mean_ms"]),
                "n_vehicles": int(r["n_vehicles"]),
            })
    federated = json.loads(fed.read_text()) if fed.exists() else {}
    return {
        "conditions": conditions,
        "federated": federated,
        "nature": ("SIMULATED — Eclipse MOSAIC ITS-G5 model, not radio hardware"),
        "source": {"delivery": "results/networking/latency.csv",
                   "federated": "results/forecasting/federated.json"},
    }


@router.get("/api/health", tags=["meta"])
def health():
    """Liveness plus data freshness — a dashboard must say when its data is stale."""
    h = readers.recorder_health()
    from core.common.data.live_providers.observatory import observatory
    live = observatory.liveness()
    cities = {k: v for k, v in live.items() if not k.startswith("_")}
    return {"status": "ok", "recorder_healthy": h.healthy, "last_tick_utc": h.last_tick_utc,
            "age_minutes": h.age_minutes,
            "live_sampling": cities, "live_sampling_healthy": bool(cities) and all(v["healthy"] for v in cities.values())}


def _pulse() -> dict:
    """A diff-sized payload: the browser already holds the tables, so only freshness and the
    latest level per corridor travel on the wire."""
    t, e = readers.traffic(), readers.evidence()
    return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "recorder": t.recorder.model_dump() if t.recorder else None,
            "corridors": [{"id": c.id, "level": c.level, "state": c.state} for c in t.corridors],
            "bins": t.bins, "span_hours": t.span_hours, "gate_passed": e.gate_passed}


@router.get("/api/stream", tags=["realtime"])
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
