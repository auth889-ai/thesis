"""How far an ambulance reaches from the city's hospitals, on the city's own Valhalla server (MIT), at map speeds; and,
for the thesis, the same at a clock time with the speeds a published dataset recorded on the roads it measured.

The city is gridded (STEP_M). One matrix call gives the map-speed time from every hospital to every grid point; the
reach within 10, 20 and 30 minutes is the grid cells inside that bound. The recorded variant never invents a speed: a
recorded site S changes the time to a point T only when the shortest path from the hospital passes S, which the matrix
tells exactly (t(H,S) + t(S,T) ≤ t(H,T) + PASS_TOLERANCE_S); the change is the stretch the site measured, re-timed with
the recorded median speed instead of the map speed on that stretch (the same rule as routing.valhalla.recorded_stretches).
Where no site lies on any path, the row says so instead of showing a difference.

    python -m core.safety.reach build --city dhaka --at 08:30     # results/reach/<city>/summary.json + evidence/reach/<city>/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import math
from datetime import datetime, timezone
from pathlib import Path

from core.common.data import city_config, real_speeds
from core.safety import hospitals as hosp
from core.simulation.ambulance import service
from core.simulation.routing import valhalla

RESULTS = service.REPO / "results/reach"
EVIDENCE = service.REPO / "evidence/reach"
BOUNDS_MIN = (10, 20, 30)
STEP_M = 500                        # grid step: a reach is counted in cells of this size, and the table says so
PASS_TOLERANCE_S = 30               # a path "passes" a site when the detour through it costs at most this much
MAX_HOSPITALS = 60                  # a build asks the server for at most this many hospitals (the emergency-tagged ones first)
LABEL = "MAP SPEEDS"


def _dest(lat: float, lon: float, bearing_deg: float, metres: float) -> tuple[float, float]:
    """The point `metres` along `bearing_deg` from (lat, lon)."""
    r, b = 6371000.0, math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(metres / r) + math.cos(p1) * math.sin(metres / r) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(metres / r) * math.cos(p1), math.cos(metres / r) - math.sin(p1) * math.sin(p2))
    return round(math.degrees(p2), 6), round(math.degrees(l2), 6)


def grid(extent_wsen: list[float], step_m: int = STEP_M) -> list[tuple[float, float]]:
    """Grid points (lat, lon) over the extent, `step_m` apart, from the south-west corner."""
    w, s, e, n = extent_wsen
    dlat = step_m / 111320.0
    dlon = step_m / (111320.0 * math.cos(math.radians((s + n) / 2)))
    pts, lat = [], s + dlat / 2
    while lat < n:
        lon = w + dlon / 2
        while lon < e:
            pts.append((round(lat, 6), round(lon, 6)))
            lon += dlon
        lat += dlat
    return pts


def chosen_hospitals(file: dict) -> tuple[list[dict], str]:
    """The hospitals a build routes from: those OpenStreetMap tags emergency=yes; if the city has none so tagged, all of
    them, up to MAX_HOSPITALS nearest the extent's centre. The note says which rule applied."""
    hs = file["hospitals"]
    tagged = [h for h in hs if h.get("emergency") == "yes"]
    if tagged:
        return tagged[:MAX_HOSPITALS], f"the {len(tagged)} hospitals OpenStreetMap tags emergency=yes" + (f", the first {MAX_HOSPITALS} by name" if len(tagged) > MAX_HOSPITALS else "")
    w, s, e, n = file["extent_wsen"]
    clat, clon = (s + n) / 2, (w + e) / 2
    hs = sorted(hs, key=lambda h: (h["lat"] - clat) ** 2 + (h["lon"] - clon) ** 2)[:MAX_HOSPITALS]
    return hs, f"no hospital carries the emergency tag in OpenStreetMap here; the {len(hs)} nearest the city centre of {file['count']}"


def recorded_sites(city_id: str, at: str) -> list[dict]:
    """The located recorded sites with a reading at `at` (the dataset's own day), each with its stretch."""
    out = []
    for src in real_speeds.recorded_sources(city_id):
        if "sites" not in src:
            continue
        reader = next(r for r in real_speeds._readers().values() if r.NAME == src["dataset"])
        for st in src["sites"]:
            if not st.get("located"):
                continue
            got = reader.reading_at(st["site"], at)
            if not got:
                continue
            out.append({"site": st["site"], "day": st["day"], "lat": st["lat"], "lon": st["lon"], "bearing_deg": st["bearing_deg"], "at": got["start"],
                        "median_kmh": got["median_kmh"], "vehicles": got["vehicles"], "stretch_m": float(got["stretch_m"]), "dataset": src["dataset"], "citation": src["citation"], "licence": src["licence"]})
    return out


def decompose(t_ht: list[list], t_hs: list[list], t_st: list[list], deltas: list[float], tol: float = PASS_TOLERANCE_S) -> tuple[list[list], list[int]]:
    """Recorded times from the map-speed matrix: for hospital h and point t, each site s whose detour costs at most
    `tol` lies on the path, and adds its stretch's delta. Returns (times, number of points changed per site). Pure."""
    out = [row[:] for row in t_ht]
    changed = [0] * len(deltas)
    for h, row in enumerate(t_ht):
        for t, base in enumerate(row):
            if base is None:
                continue
            for s, delta in enumerate(deltas):
                a, b = t_hs[h][s], t_st[s][t]
                if a is not None and b is not None and a + b <= base + tol:
                    out[h][t] = out[h][t] + delta
                    changed[s] += 1
    return out, changed


def _counts(times: list[list], bounds=BOUNDS_MIN) -> list[dict]:
    return [{str(b): sum(1 for t in row if t is not None and t <= 60 * b) for b in bounds} for row in times]


def _best(times: list[list]) -> list:
    """For each point, the time from the nearest hospital."""
    cols = zip(*times) if times else []
    return [min((t for t in col if t is not None), default=None) for col in cols]


def plain_numbers(best_map: list, best_rec: list | None, n_points: int, bounds=BOUNDS_MIN) -> dict:
    """The everyday sentence's numbers, from the per-point best times and nothing else: the share of the city's grid
    an ambulance from its nearest hospital reaches within each bound."""
    pct = lambda best: {str(b): round(100 * sum(1 for t in best if t is not None and t <= 60 * b) / max(n_points, 1), 1) for b in bounds}
    return {"map_pct": pct(best_map), "recorded_pct": pct(best_rec) if best_rec is not None else None, "grid_points": n_points}


def build(city_id: str, at: str = "08:30", profile: str = "car", step_m: int = STEP_M, root: Path = RESULTS, evidence: Path | None = EVIDENCE) -> dict:
    cfg = city_config.load(city_id)
    file = hosp.load(city_id)
    if not file:
        return {"city_id": city_id, "available": False, "reason": "no data for this city: no hospitals file (python -m core.safety.hospitals --city <id>)"}
    hs, rule = chosen_hospitals(file)
    pts = grid(file["extent_wsen"], step_m)
    m = valhalla.matrix(city_id, [(h["lat"], h["lon"]) for h in hs], pts, profile)
    if not m["available"]:
        return {"city_id": city_id, "available": False, "reason": m["note"], "code": m["code"]}
    t_ht = m["times_s"]
    sites = recorded_sites(city_id, at)
    rec, changed, deltas, t_rec = None, [], [], None
    if sites:
        for s in sites:                                   # the map speed on the measured stretch: the server's own time over it, along the site's bearing
            end = _dest(s["lat"], s["lon"], s["bearing_deg"], s["stretch_m"])
            leg = valhalla.matrix(city_id, [(s["lat"], s["lon"])], [end], profile)
            t_leg, d_leg = (leg["times_s"][0][0], leg["distances_m"][0][0]) if leg["available"] else (None, None)
            map_mps = d_leg / t_leg if t_leg and d_leg else None
            s["map_kmh_on_stretch"] = round(map_mps * 3.6, 1) if map_mps else None
            s["delta_s"] = round(s["stretch_m"] / (s["median_kmh"] / 3.6) - s["stretch_m"] / map_mps, 1) if map_mps else 0.0
            deltas.append(s["delta_s"])
        hs_m = valhalla.matrix(city_id, [(h["lat"], h["lon"]) for h in hs], [(s["lat"], s["lon"]) for s in sites], profile)
        st_m = valhalla.matrix(city_id, [(s["lat"], s["lon"]) for s in sites], pts, profile)
        if hs_m["available"] and st_m["available"]:
            t_rec, changed = decompose(t_ht, hs_m["times_s"], st_m["times_s"], deltas)
            rec = _counts(t_rec)
    cell_km2 = (step_m / 1000) ** 2
    counts = _counts(t_ht)
    rows = []
    for i, h in enumerate(hs):
        rows.append({"osm_id": h["osm_id"], "name": h["name"], "emergency": h.get("emergency"), "lat": h["lat"], "lon": h["lon"],
                     "map_cells": counts[i], "map_km2": {k: round(v * cell_km2, 1) for k, v in counts[i].items()},
                     "recorded_cells": rec[i] if rec else None, "recorded_km2": {k: round(v * cell_km2, 1) for k, v in rec[i].items()} if rec else None,
                     "points_changed": sum(1 for a, b in zip(t_ht[i], t_rec[i]) if a != b) if t_rec else None})
    best_map, best_rec = _best(t_ht), _best(t_rec) if t_rec else None
    out = {"city_id": city_id, "available": True, "label": LABEL, "built_utc": datetime.now(timezone.utc).isoformat(), "engine": valhalla.ENGINE, "profile": profile,
           "time_source": valhalla.TIME_SOURCE, "extract": {"path": cfg.routing.extract, "date": cfg.routing.extract_date} if cfg.routing else None, "credit": cfg.routing.credit if cfg.routing else None,
           "hospitals_file": {"count": file["count"], "sha256": file["sha256"], "fetched_utc": file["fetched_utc"], "rule": rule}, "grid": {"step_m": step_m, "points": len(pts), "extent_wsen": file["extent_wsen"], "cell_km2": cell_km2},
           "bounds_min": list(BOUNDS_MIN), "recorded": {"at": at, "sites": sites, "points_changed_per_site": changed, "pass_tolerance_s": PASS_TOLERANCE_S,
                                                        "note": None if sites else "no recorded site with a reading at this time in this city: the recorded variant does not exist here"},
           "rows": rows, "points": [{"lat": a, "lon": b, "map_s": m_, "recorded_s": r_} for (a, b), m_, r_ in zip(pts, best_map, best_rec or [None] * len(pts))]}
    out["plain"] = plain_numbers(best_map, best_rec, len(pts))
    body = json.dumps(out, sort_keys=True)
    out["sha256"] = hashlib.sha256(body.encode()).hexdigest()
    folder = Path(root) / city_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(json.dumps(out, indent=1))
    if evidence:
        ev = Path(evidence) / city_id
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "summary.json").write_text(json.dumps(out, indent=1))
        (ev / "summary.sha256").write_text(out["sha256"] + "\n")
        (ev / "hospitals.sha256").write_text(file["sha256"] + "\n")
    return out


def read(city_id: str, root: Path = RESULTS, with_points: bool = True) -> dict:
    f = Path(root) / city_id / "summary.json"
    if not f.exists():
        return {"city_id": city_id, "available": False, "reason": "no data for this city: the reach has not been built (python -m core.safety.reach build --city <id>)"}
    d = json.loads(f.read_text())
    if not with_points:
        d.pop("points", None)
    return d


def nearest(city_id: str, lat: float, lon: float, k: int = 3, profile: str = "car") -> dict:
    """The k hospitals nearest a point by drive time at map speeds, from the server, with the hospitals file as targets (animal hospitals left out)."""
    file = hosp.load(city_id)
    if not file:
        return {"city_id": city_id, "available": False, "code": "no_hospitals", "note": "no data for this city: no hospitals file"}
    hs, animal = hosp.for_people(file["hospitals"])
    hs, not_for_patients = hosp.for_a_patient(hs)
    hs = hosp.one_each(hs)
    m = valhalla.matrix(city_id, [(lat, lon)], [(h["lat"], h["lon"]) for h in hs], profile)
    if not m["available"]:
        return m
    ranked = sorted((j for j in range(len(hs)) if m["times_s"][0][j] is not None), key=lambda j: m["times_s"][0][j])[:k]
    return {"city_id": city_id, "available": True, "engine": valhalla.ENGINE, "time_source": valhalla.TIME_SOURCE, "origin": {"lat": lat, "lon": lon}, "hospitals_considered": len(hs), "animal_hospitals_left_out": [h["name"] for h in animal],
            "not_for_a_patient_left_out": [h["name"] for h in not_for_patients],
            "nearest": [{**{x: hs[j][x] for x in ("osm_id", "name", "lat", "lon", "emergency")}, "time_s": m["times_s"][0][j], "distance_m": m["distances_m"][0][j]} for j in ranked]}


def live(city_id: str, lat: float, lon: float, k: int = 3, profile: str = "car", iso=None) -> dict:
    """Live reach from a tapped point (step K, 2026-10-11): the k nearest hospitals by drive time, then each one's 10/20/30-minute
    polygons from the city's own routing server (Valhalla's isochrone API, docs/docs/api/isochrone), and the ambulance-direction drive
    time hospital -> point. Computed on the request and timed; the thesis's shares (`read(...)["plain"]`, the saved build) are
    returned beside it, never replaced. `iso` lets the router cache per hospital."""
    t0 = time.perf_counter()
    near = nearest(city_id, lat, lon, k=k, profile=profile)
    if not near.get("available"):
        return near
    iso = iso or valhalla.isochrone
    hs = near["nearest"]
    back = valhalla.matrix(city_id, [(h["lat"], h["lon"]) for h in hs], [(lat, lon)], profile)
    cached = 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, len(hs))) as ex:            # the hospitals' isochrones in parallel: one server round trip, not k
        answers = list(ex.map(lambda h: iso(city_id, h["lat"], h["lon"]), hs))
    for i, (h, got) in enumerate(zip(hs, answers)):
        if isinstance(got, tuple):                                   # (result, was_cached) from the router's cache
            got, was = got
            cached += int(was)
        h["contours"] = got.get("contours", []) if got.get("available") else []
        h["to_point_s"] = back["times_s"][i][0] if back.get("available") else None
        h["reached_within_min"] = next((m for m in (10, 20, 30) if h["to_point_s"] is not None and h["to_point_s"] <= m * 60), None)
    saved = read(city_id, with_points=False)
    return {**{x: near[x] for x in ("city_id", "available", "engine", "time_source", "origin")}, "label": "LIVE", "hospitals": hs,
            "computed_s": round(time.perf_counter() - t0, 2), "isochrones_cached": cached,
            "thesis": {"map_pct": saved["plain"]["map_pct"], "grid_points": saved["plain"].get("grid_points"), "at": saved.get("recorded", {}).get("at")} if saved.get("available") and "plain" in saved else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--city", required=True); b.add_argument("--at", default="08:30"); b.add_argument("--step", type=int, default=STEP_M)
    a = ap.parse_args()
    got = build(a.city, a.at, step_m=a.step)
    print(json.dumps({k: got.get(k) for k in ("available", "reason", "plain", "sha256")}, indent=1), f"rows={len(got.get('rows', []))}")
