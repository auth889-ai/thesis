"""Ingest shared location fixes, snap them, bin them into road-direction cells, and read the cells back."""
from __future__ import annotations

import hashlib
import math
import statistics
from datetime import datetime, timedelta, timezone

import h3
from sqlalchemy import delete, func, select

from app.lifeos.db import session
from app.probes.db import H3_RES, RETAIN_HOURS, ProbeCellRow, ProbePointRow
from app.probes.snap import Snapper, default

BIN_MIN = 5
MAX_SPEED_KMH = 160                  # faster than any road in a city: a GPS glitch, dropped
MIN_ACCURACY_M = 60                  # a fix this uncertain cannot say which road it is on


def device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()[:16]


def _parse(ts: str) -> datetime:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _haversine_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cell_of(lat: float, lng: float, heading: float | None) -> str:
    octant = "x" if heading is None else str(int(((heading % 360) + 22.5) // 45) % 8)
    return f"{h3.latlng_to_cell(lat, lng, H3_RES)}:{octant}"


def _bin(ts: datetime) -> datetime:
    return ts.replace(minute=(ts.minute // BIN_MIN) * BIN_MIN, second=0, microsecond=0)


def prepare(points: list[dict]) -> list[dict]:
    """Order by time, derive a speed where the device gave none, drop fixes that cannot be trusted."""
    pts = sorted((dict(p) for p in points), key=lambda p: p["recorded_at"])
    out, prev = [], None
    for p in pts:
        p["recorded_at"] = p["recorded_at"] if isinstance(p["recorded_at"], str) else p["recorded_at"].isoformat()
        if p.get("accuracy_m") is not None and p["accuracy_m"] > MIN_ACCURACY_M:
            continue
        if p.get("speed_kmh") is None and prev is not None:
            dt = (_parse(p["recorded_at"]) - _parse(prev["recorded_at"])).total_seconds()
            if 1 <= dt <= 120:
                p["speed_kmh"] = round(_haversine_km(prev["lat"], prev["lng"], p["lat"], p["lng"]) / dt * 3600, 1)
        if p.get("speed_kmh") is not None and not (0 <= p["speed_kmh"] <= MAX_SPEED_KMH):
            continue
        out.append(p)
        prev = p
    return out


def ingest(device_id: str, city: str, points: list[dict], snapper: Snapper | None = None, db_url: str | None = None) -> dict:
    snapper = snapper or default()
    pts = snapper.snap(prepare(points)) if points else []
    now = datetime.now(timezone.utc)
    dev = device_hash(device_id)
    touched: set[tuple[str, datetime]] = set()
    with session(db_url) as s:
        for p in pts:
            lat, lng = (p["snapped_lat"], p["snapped_lng"]) if p.get("snapped_lat") is not None else (p["lat"], p["lng"])
            cell = cell_of(lat, lng, p.get("heading"))
            rec = _parse(p["recorded_at"])
            s.add(ProbePointRow(device=dev, city=city, recorded_at=rec, received_at=now, lat=p["lat"], lng=p["lng"],
                                accuracy_m=p.get("accuracy_m"), heading=p.get("heading"), speed_kmh=p.get("speed_kmh"),
                                snapped_lat=p.get("snapped_lat"), snapped_lng=p.get("snapped_lng"), snap_confidence=p.get("snap_confidence"),
                                snapper=snapper.name, cell=cell))
            touched.add((cell, _bin(rec)))
        s.flush()
        for cell, b in touched:
            rows = s.execute(select(ProbePointRow.device, ProbePointRow.speed_kmh).where(
                ProbePointRow.cell == cell, ProbePointRow.recorded_at >= b, ProbePointRow.recorded_at < b + timedelta(minutes=BIN_MIN))).all()
            speeds = [r.speed_kmh for r in rows if r.speed_kmh is not None]
            lat, lng = h3.cell_to_latlng(cell.split(":")[0])
            agg = s.get(ProbeCellRow, (cell, b)) or ProbeCellRow(cell=cell, bin_start=b, city=city, lat=lat, lng=lng)
            agg.n_points, agg.n_devices = len(rows), len({r.device for r in rows})
            agg.mean_speed_kmh = round(statistics.fmean(speeds), 1) if speeds else None
            agg.p50_speed_kmh = round(statistics.median(speeds), 1) if speeds else None
            agg.updated_at = now
            s.add(agg)
        s.execute(delete(ProbePointRow).where(ProbePointRow.received_at < now - timedelta(hours=RETAIN_HOURS)))
        s.commit()
    return {"accepted": len(pts), "dropped": len(points) - len(pts), "cells_updated": len(touched), "snapper": snapper.name,
            "snapped": sum(1 for p in pts if p.get("snapped_lat") is not None), "device": dev}


def cells(city: str, minutes: int = 30, db_url: str | None = None) -> dict:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    with session(db_url) as s:
        rows = s.execute(select(ProbeCellRow).where(ProbeCellRow.city == city, ProbeCellRow.bin_start >= _bin(since))
                         .order_by(ProbeCellRow.bin_start.desc())).scalars().all()
    latest: dict[str, ProbeCellRow] = {}
    for r in rows:
        latest.setdefault(r.cell, r)
    return {"city": city, "window_min": minutes, "cells": [
        {"cell": r.cell, "lat": r.lat, "lng": r.lng, "bin_start": r.bin_start.isoformat(), "n_points": r.n_points, "n_devices": r.n_devices,
         "mean_speed_kmh": r.mean_speed_kmh, "p50_speed_kmh": r.p50_speed_kmh, "heading_octant": r.cell.split(":")[1]} for r in latest.values()]}


def status(city: str, db_url: str | None = None) -> dict:
    with session(db_url) as s:
        n_points = s.execute(select(func.count()).select_from(ProbePointRow).where(ProbePointRow.city == city)).scalar_one()
        n_cells = s.execute(select(func.count()).select_from(ProbeCellRow).where(ProbeCellRow.city == city)).scalar_one()
        n_devices = s.execute(select(func.count(func.distinct(ProbePointRow.device))).where(ProbePointRow.city == city)).scalar_one()
        last = s.execute(select(func.max(ProbeCellRow.updated_at)).where(ProbeCellRow.city == city)).scalar_one()
    sn = default()
    return {"city": city, "points_retained": n_points, "cells": n_cells, "devices_retained": n_devices,
            "last_update": last.isoformat() if last else None, "snapper": sn.name,
            "snapping": "Amazon Location SnapToRoads" if sn.name == "amazon_location" else "not configured: raw positions are binned, labelled unsnapped",
            "cell": f"H3 resolution {H3_RES} (about 70 m) x heading octant", "retention": f"raw fixes {RETAIN_HOURS} h, cells kept"}
