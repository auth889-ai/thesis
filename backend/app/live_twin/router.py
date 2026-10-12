"""The live twin (core/simulation/live_twin): a running SUMO simulation with three forecasters running alongside it (scored live, not steering it), labelled SIMULATION.
Vehicles and forecasts stream over a WebSocket (sumo-web3d's delta approach); clicks and settings come back the same way, or over
POST .../command for scripts."""
from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.platform.ratelimit import visitor
from core.simulation.live_twin.manager import MANAGER
from core.simulation.live_twin.session import Refused

router = APIRouter()
POLL_S = 0.1
VISITOR_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def who(request_or_ws, given: str | None = None) -> str:
    """The visitor a twin belongs to: the browser's own random id (kept in its storage, sent as X-TT-Visitor or ?v=), else the client
    address. Not the address alone: a phone or home connection can alternate between addresses (seen 2026-10-10: .178 and .179), which
    made one visitor two. The hosted per-day start limit stays per address (backend/app/platform/ratelimit.py)."""
    v = given if given is not None else request_or_ws.headers.get("x-tt-visitor")
    return f"v:{v}" if v and VISITOR_ID.match(v) else visitor(request_or_ws)


@router.post("/api/live-twin/{city_id}/start", tags=["simulation"])
def start(city_id: str, request: Request, payload: dict | None = None):
    """Start this visitor's twin (seeded from the clock), or return the one already running for them."""
    p = payload or {}
    try:
        s, created = MANAGER.start(city_id, who(request), speed=float(p.get("speed", 8)), technology=p.get("technology", "its_g5"))
    except Refused as exc:
        raise HTTPException(409 if exc.key == "full" else 400, {"message": str(exc), "key": exc.key, "params": exc.params}) from None
    return {**s.hello(), "created": created}


def _mine(sid: str, request_visitor: str):
    s = MANAGER.get(sid)
    if not s:
        raise HTTPException(404, "no such twin")
    if s.visitor != request_visitor:
        raise HTTPException(403, "this twin belongs to another visitor")
    return s


@router.get("/api/live-twin/twins/{sid}", tags=["simulation"])
def state(sid: str, request: Request):
    """The twin's settings, roads and current status (the WebSocket streams the rest)."""
    s = _mine(sid, who(request))
    return {**s.hello(), **s._status()}


@router.post("/api/live-twin/twins/{sid}/command", tags=["simulation"])
def command(sid: str, request: Request, payload: dict):
    """crash {lon, lat} | clear_crashes | ambulance {lon, lat[, to_lon, to_lat]} | demand {value} | technology {value} | speed {value} | stop"""
    _mine(sid, who(request)).command(payload)
    return {"queued": payload.get("cmd")}


@router.post("/api/live-twin/twins/{sid}/stop", tags=["simulation"])
def stop(sid: str, request: Request):
    _mine(sid, who(request)).stop()
    return {"stopping": sid}


@router.websocket("/api/live-twin/twins/{sid}/ws")
async def stream(ws: WebSocket, sid: str):
    s = MANAGER.get(sid)
    me = who(ws, ws.query_params.get("v"))
    await ws.accept()
    if not s or s.visitor != me:
        await ws.send_text(json.dumps({"type": "error", "message": "no such twin for this visitor"}))
        await ws.close()
        return
    await ws.send_text(json.dumps(s.hello()))
    index = None

    async def receive():
        while True:
            msg = json.loads(await ws.receive_text())
            s.command(msg)

    reader = asyncio.create_task(receive())
    try:
        while True:
            index, msgs = s.since(index)
            for m in msgs:
                await ws.send_text(json.dumps(m, separators=(",", ":")))
            if s.status in ("stopped", "failed") and not msgs:
                break
            if reader.done():
                reader.result()                                       # raises WebSocketDisconnect when the page went away
            await asyncio.sleep(POLL_S)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader.cancel()
        try:
            await ws.close()
        except RuntimeError:
            pass
