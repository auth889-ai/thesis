"""ANALYZE TRAFFIC: one origin, one destination, one departure — current state, forecast, decision.

    job = start({"origin": "farmgate", "destination": "gulshan1", "horizon_min": 30})
    status(job)  -> {"stage": "Running forecast", ...} then {"stage": "done", "result": {...}}

Each stage is real work and is reported as it happens:
    Fetching traffic          live traffic-aware routes and the current corridor state (Google)
    Running forecast          the registry's model over the recorded window, per corridor
    Evaluating alternatives   every alternative priced with forecast-derived future edge costs

A route is priced from the forecast only where it actually runs along an observed corridor; a
route with no observed corridor keeps its current ETA and says "no forecast coverage" — the
prediction is never extended to roads nobody measured. Confidence is the model's measured class
accuracy on this city's own recorded data at that horizon (E1), not a guess.
"""
from __future__ import annotations

import json
import math
import re
import sys
import threading
import uuid
from datetime import datetime, timezone

from backend.app import config
from backend.app.datasets import reference_corridors as cz

sys.path.insert(0, str(config.REPO))

HORIZONS = [15, 30, 60]
NEAR_M = 300              # a route "runs along" a corridor if it passes this close to its axis
MIN_POINTS = 3
BAND = {0: 1.08, 1: 1.33, 2: 1.75, 3: 2.50}
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


# ------------------------------------------------------------------ geometry
def _m(lat1, lng1, lat2, lng2) -> float:
    dy = (lat2 - lat1) * 111_000
    dx = (lng2 - lng1) * 111_000 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _dist_to_segment(p, a, b) -> tuple[float, float]:
    """(metres from point p to segment a-b, position t along it), all (lat, lng), flat frame."""
    ky = 111_000; kx = 111_000 * math.cos(math.radians(a[0]))
    px, py = (p[1] - a[1]) * kx, (p[0] - a[0]) * ky
    bx, by = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky
    L2 = bx * bx + by * by
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * bx + py * by) / L2))
    return math.hypot(px - t * bx, py - t * by), t


def _min_dist(p, line) -> float:
    return min(_dist_to_segment(p, line[k], line[k + 1])[0] for k in range(len(line) - 1))


def runs_along(pts, poly, near_m: float = NEAR_M, min_cover: float = 0.5) -> bool:
    """A route runs along a corridor when at least `min_cover` of the corridor's own polyline
    vertices lie within `near_m` of the route — the live geometry, not a straight axis, so a
    curved road counts and a junction touch does not."""
    if len(poly) < 2 or len(pts) < 2:
        return False
    covered = sum(1 for v in poly if _min_dist(v, pts) <= near_m)
    return covered / len(poly) >= min_cover


def multiplier(level: float) -> float:
    lo, hi = int(max(0, min(3, math.floor(level)))), int(max(0, min(3, math.ceil(level))))
    return BAND[lo] if lo == hi else BAND[lo] + (level - lo) * (BAND[hi] - BAND[lo])


# ------------------------------------------------------------------ places
def _usable(c: dict) -> bool:
    """A corridor the analysis may price from: live now, or carrying a recorded state."""
    return bool(c.get("is_live") or c.get("has_state"))


def is_dhaka(city: str) -> bool:
    return re.sub(r"[^a-z]", "", (city or "").lower()) in ("dhaka", "dhakabangladesh", "dhakar")


def city_id_for(city: str) -> str | None:
    """The registry id of a typed city name, if it is registered (no geocoding here)."""
    if is_dhaka(city):
        return "dhaka"
    from pipeline.city.registry import registry, slug
    key = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    hits = []
    for cid in registry.list_ids():
        sp = registry.get(cid)
        names = {cid, slug(sp.display_name or ""), (sp.display_name or "").split(",")[0]}
        if key in {re.sub(r"[^a-z0-9]", "", n.lower()) for n in names if n}:
            hits.append(cid)
    if not hits:
        return None
    try:                                    # the one already being observed wins
        from backend.app.live import observatory as obs_mod
        watched = set(obs_mod.observatory.cities())
        hits.sort(key=lambda c: (c not in watched, len(c)))
    except Exception:                       # noqa: BLE001
        pass
    return hits[0]


def levels_from_speeds(cd, forecast: dict | None, live: dict) -> tuple[dict, dict]:
    """Observatory speeds (m/s) -> congestion levels per corridor, now and per horizon, using
    each corridor's own free-flow speed from the live snapshot. Same bands as the recorder."""
    import numpy as np
    from backend.app.live.google_routes import classify
    LV = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5}
    free = {}
    for c in live.get("corridors", []):
        if c.get("static_duration_s") and c.get("distance_m"):
            free[c["id"]] = float(c["distance_m"]) / float(c["static_duration_s"])
    obs, pred = {}, {hh: {} for hh in HORIZONS}
    vals = np.asarray(cd.values) if cd.shape[0] else None
    for i, cid in enumerate(cd.node_ids):
        f0 = free.get(cid)
        if not f0:
            continue
        if vals is not None:
            col = vals[:, i]; fin = col[np.isfinite(col)]
            if fin.size:
                obs[cid] = LV[classify(f0 / max(float(fin[-1]), 0.1), 1.0)]
        if forecast:
            for hh in HORIZONS:
                v = (forecast["values"].get(hh) or forecast["values"].get(str(hh)) or [None] * len(cd.node_ids))[i]
                if v is not None and v == v:
                    pred[hh][cid] = LV[classify(f0 / max(float(v), 0.1), 1.0)]
    return obs, pred


_CITY_BOX: dict[str, dict] = {}


_GEO_CACHE: dict[str, list] = {}
_GEO_LOCK = threading.Lock()
_GEO_LAST = [0.0]


def _nominatim(params: dict) -> list[dict]:
    """One query to OpenStreetMap's geocoder, at most one per second (their usage policy), with the
    answer cached for the process: the same place typed twice is not two network calls, and a
    burst of suggestion requests cannot starve the resolve that follows."""
    import time
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"format": "json", **params})
    with _GEO_LOCK:
        if q in _GEO_CACHE:
            return _GEO_CACHE[q]
        wait = 1.05 - (time.monotonic() - _GEO_LAST[0])
        if wait > 0:
            time.sleep(wait)                              # the geocoder's rate limit, not a cosmetic delay
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}",
                                     headers={"User-Agent": "traffictwin/1.0 (research)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hits = json.loads(r.read().decode())
        finally:
            _GEO_LAST[0] = time.monotonic()
        if hits:
            _GEO_CACHE[q] = hits
        return hits


def city_box(city: str) -> dict | None:
    """The city itself, geocoded once: centre + bounding box, so places are searched INSIDE it."""
    key = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    if key in _CITY_BOX:
        return _CITY_BOX[key]
    if is_dhaka(city):
        box = {"label": "Dhaka", "lat": 23.78, "lng": 90.40, "bbox": [90.30, 23.66, 90.52, 23.92]}
    else:
        hits = _nominatim({"q": city, "limit": 6, "accept-language": "en"})
        if not hits:
            return None
        # Nominatim's first hit is not always the city of that name (an alias can outrank it):
        # prefer a hit whose own name matches what was typed, then a settlement, then the first.
        def name_ok(h):
            return re.sub(r"[^a-z0-9]", "", h.get("display_name", "").split(",")[0].lower()) == key
        def settlement(h):
            return h.get("type") in ("city", "town", "administrative", "municipality", "village")
        h = next((x for x in hits if name_ok(x) and settlement(x)), None) or next((x for x in hits if name_ok(x)), None) \
            or next((x for x in hits if settlement(x)), None) or hits[0]
        bb = [float(x) for x in h["boundingbox"]]                        # south, north, west, east
        box = {"label": h.get("display_name", city).split(",")[0], "lat": float(h["lat"]), "lng": float(h["lon"]),
               "bbox": [bb[2], bb[0], bb[3], bb[1]]}                  # west, south, east, north
    _CITY_BOX[key] = box
    return box


def resolve_place(text: str, city: str = "dhaka") -> dict:
    """'lat, lng' | a known Dhaka place | the city itself | free text via OpenStreetMap's geocoder
    bounded to the city. Never silent: an unknown place is an error the page shows, with a hint."""
    t = (text or "").strip()
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", t)
    if m:
        return {"lat": float(m.group(1)), "lng": float(m.group(2)), "label": t, "source": "coordinates"}
    key = re.sub(r"[^a-z0-9]", "", t.lower())
    if is_dhaka(city):
        for name, (lat, lng) in cz.PLACES.items():
            if key == re.sub(r"[^a-z0-9]", "", name.lower()):
                return {"lat": lat, "lng": lng, "label": name, "source": "known place"}
    box = city_box(city)
    if box is None:
        raise ValueError(f"could not find the city '{city}'")
    if key == re.sub(r"[^a-z0-9]", "", box["label"].lower()) or key == re.sub(r"[^a-z0-9]", "", (city or "").lower()):
        return {"lat": box["lat"], "lng": box["lng"], "label": f"{box['label']} (centre)", "source": "city centre"}
    hits = _search_in(box, t, 1)
    if not hits:
        raise ValueError(f"'{t}' was not found inside {box['label']}. Type a place in {box['label']} "
                         f"(pick one of the suggestions as you type), or 'lat, lng'.")
    return {"lat": float(hits[0]["lat"]), "lng": float(hits[0]["lon"]),
            "label": hits[0].get("display_name", t).split(",")[0], "source": "OpenStreetMap geocoder"}


def _search_in(box: dict, q: str, limit: int) -> list[dict]:
    """Places matching `q` inside the city: first strictly bounded to its box, then the looser
    '<q>, <city>' query (Nominatim needs the city word for short names) filtered to the box."""
    w, s_, e, n = box["bbox"]
    common = {"limit": limit, "accept-language": "en"}
    hits = _nominatim({"q": q, "viewbox": f"{w},{n},{e},{s_}", "bounded": 1, **common})
    if not hits:
        cand = _nominatim({"q": f"{q}, {box['label']}", "viewbox": f"{w},{n},{e},{s_}", **common})
        hits = [h for h in cand if w <= float(h["lon"]) <= e and s_ <= float(h["lat"]) <= n]
    return hits


def suggest(city: str, q: str, limit: int = 8) -> list[dict]:
    """Place suggestions for the origin / destination inputs, inside the named city."""
    q = (q or "").strip()
    out = []
    if is_dhaka(city):
        for k, v in cz.PLACES.items():
            lab = k.replace("_", " ").title()
            if not q or q.lower() in lab.lower():
                out.append({"label": lab, "lat": v[0], "lng": v[1], "source": "known place"})
    if len(q) < 2:
        return out[:limit]
    box = city_box(city)
    if box is None:
        return out[:limit]
    try:
        hits = _search_in(box, q, limit)
    except Exception:                                   # noqa: BLE001 - suggestions are best effort
        hits = []
    seen = {o["label"] for o in out}
    for h in hits:
        parts = [x.strip() for x in h.get("display_name", "").split(",")]
        lab = ", ".join(parts[:2]) if parts else q
        if lab not in seen:
            seen.add(lab)
            out.append({"label": lab, "lat": float(h["lat"]), "lng": float(h["lon"]), "source": "OpenStreetMap"})
    return out[:limit]


def places() -> list[dict]:
    return [{"id": k, "label": k.replace("_", " ").title(), "lat": v[0], "lng": v[1]}
            for k, v in cz.PLACES.items()]


# ------------------------------------------------------------------ the analysis
def _corridor_polylines(live: dict) -> dict[str, list]:
    """Each corridor's road geometry from the live snapshot; the straight axis if it has none."""
    live_by_id = {c["id"]: c for c in live.get("corridors", [])}
    out = {}
    for c in cz.CORRIDORS:
        poly = [tuple(p) for s in ((live_by_id.get(c["id"]) or {}).get("segments") or [])
                for p in (s.get("coordinates") or [])]
        if len(poly) < 2:
            poly = list(cz.coords(c))
        out[c["id"]] = poly
    return out


def _accuracy(model: str) -> dict:
    f = config.REPO / "results/forecasting/live_backtest.json"
    if not f.exists():
        return {}
    bt = json.loads(f.read_text())
    return {r["horizon_min"]: r for r in bt["rows"] if r["model"] == model}


def _run(job: str, p: dict) -> None:
    def emit(**kw):
        with _LOCK:
            _JOBS[job].update(kw)
    try:
        city = p.get("city") or "dhaka"
        from backend.app.datasets import forecast_inputs as dataset_ops
        scope = dataset_ops.scope_for(city)
        if scope:                                       # an uploaded city dataset: the chosen checkpoint runs
            res = dataset_ops.analyze_dataset(p, scope, emit, run_id=job)
            emit(status="done", stage="done", result=res)
            return
        from traffictwin.data import provenance as pv
        run = pv.Run(job, city=city, origin=p.get("origin"), destination=p.get("destination"), requested_model=p.get("model") or "auto",
                     horizon_min=int(p.get("horizon_min") or 30), request=p)
        horizon = int(p.get("horizon_min") or 30)
        dep = p.get("departure")
        lead = horizon
        if dep:
            try:
                d = datetime.fromisoformat(dep)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                lead = max(horizon, int((d - datetime.now(timezone.utc)).total_seconds() // 60))
            except ValueError:
                pass
        h = min([x for x in HORIZONS if x >= lead] or [60])

        model_req = (p.get("model") or "").strip() or None      # a specific model, or the registry's forecast decision
        from backend.app.forecasting import model_registry
        product = model_registry.state(city_id_for(city) or city)
        if not model_req or model_req.lower() in ("auto", "best"):
            model_req = product["forecast"]["model"] if product["forecast"]["model"] not in ("persistence",) else None
        run.stage("Resolving city", emit)
        o = resolve_place(p.get("origin") or "farmgate", city)
        d = resolve_place(p.get("destination") or "shahbagh", city)
        run.set(origin_resolved=o, destination_resolved=d)
        run.stage("Validating traffic data", emit)
        from backend.app.live.google_routes import service
        routes = service.routes((o["lat"], o["lng"]), (d["lat"], d["lng"])) if service.configured else {"is_live": False, "routes": [], "request_status": "NOT_CONFIGURED", "source": "google_routes"}
        corr = service.corridors() if routes.get("is_live") else {"is_live": False, "corridors": [], "request_status": routes.get("request_status")}
        traffic_basis = "LIVE"
        if not routes.get("is_live") or not routes.get("routes"):
            # NO KEY / DENIED / OVER QUOTA: the application keeps working on its own road network and its
            # own recorded corridor states. Everything downstream is labelled RECORDED, never live.
            from backend.app.routing import local_routes
            live_status = routes.get("request_status")
            if not local_routes.router.available:
                run.finish("failed", f"live routing unavailable: {live_status}; no local road network either")
                raise RuntimeError(f"live routing unavailable: {live_status}; no local road network either")
            levels, as_of_utc = local_routes.recorded_state("dhaka") if is_dhaka(city) else ({}, None)
            from backend.app.datasets import reference_corridors as _rc
            defs = [_rc.describe(c) for c in _rc.CORRIDORS] if is_dhaka(city) else []
            corr = local_routes.router.corridors(defs, levels, as_of_utc)
            state = {c["id"]: {"edges": set(e.getID() for e in local_routes.router.corridor_route(c["id"], (c["origin"]["lat"], c["origin"]["lng"]), (c["destination"]["lat"], c["destination"]["lng"]))), "level": c.get("level")}
                     for c in corr["corridors"] if c.get("sumo_mapped")}
            routes = local_routes.router.routes((o["lat"], o["lng"]), (d["lat"], d["lng"]), state, as_of_utc)
            if not routes.get("routes"):
                run.finish("failed", f"live routing unavailable: {live_status}; local router: {routes.get('request_status')}")
                raise RuntimeError(f"live routing unavailable: {live_status}; local router: {routes.get('request_status')}")
            traffic_basis = f"RECORDED corridor states as of {as_of_utc}" if as_of_utc else "FREE-FLOW (no recorded traffic for this city)"
            emit(traffic_basis=traffic_basis, live_status=live_status)
            run.set(live_routing_status=live_status, traffic_basis=traffic_basis)
        run.set(routes_retrieved_at=routes.get("retrieved_at"), routes_n=len(routes.get("routes") or []))
        run.set(routing_provider=routes.get("source"), routing_preference=routes.get("routing_preference"), routing_request_status=routes.get("request_status"),
                routing_backend_function=("backend/app/live/google_routes.py: LiveService.routes -> Google Routes API computeRoutes" if routes.get("source") == "google_routes"
                                          else "backend/app/routing/local_routes.py: LocalRouter.routes -> sumolib shortest paths on the frozen Dhaka network, penalty-method alternatives"), routing_latency_ms=routes.get("request_latency_ms"),
                route_geometry_hash=pv.sha_json([[pt for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])] for r in routes["routes"]]),
                routes_summary=[{"key": "ABC"[i], "distance_m": r.get("distance_m"), "duration_s": r.get("duration_s"), "static_duration_s": r.get("static_duration_s"),
                                 "points": sum(len(s.get("coordinates") or []) for s in (r.get("segments") or []))} for i, r in enumerate(routes["routes"][:3])])
        run.stage("Loading checkpoint", emit)
        dhaka = is_dhaka(city)
        cid = city_id_for(city)
        from backend.app.live import observatory as obs_mod
        observe = {"city_id": cid, "watched": bool(cid) and cid in obs_mod.observatory.cities(),
                   "steps_have": obs_mod.observatory.readiness(cid)["steps_have"] if cid else 0}
        if dhaka:
            from pipeline.routing.forecast_to_costs import recorded_forecast
            fc = recorded_forecast("dhaka", HORIZONS, model_req, "latest")
            f = fc.get("forecast") or {}
            pred = {hh: dict(zip(f.get("node_ids", []), f["values"].get(hh) or f["values"].get(str(hh)) or []))
                    for hh in HORIZONS} if f else {hh: {} for hh in HORIZONS}
            observed = dict((fc.get("observed") or {}).get("levels") or {})
        elif cid and observe["steps_have"] >= 1:
            # a city sir asked us to observe: its own corridors, its own live history, the same
            # forecast interface — persistence from the first sample, Chronos from the eighth
            from pipeline.forecasting.adapters.registry import forecast as run_forecast
            cd_city = obs_mod.observatory.city_data(cid)
            corr = service.corridors_for(cid)
            fc = run_forecast(cd_city, HORIZONS, model_req)
            f = fc.get("forecast") or {}
            fc["input"] = cd_city.describe()
            observed, pred = levels_from_speeds(cd_city, f or None, corr)
        else:
            fc = {"forecast": None, "observed": {}, "input": {}}
            f = {}; pred = {hh: {} for hh in HORIZONS}; observed = {}
        forecastable = bool(f)
        run.set(resolved_model=f.get("model") if f else "none", checkpoint_path=f.get("checkpoint") if f else None,
                dataset_hash=pv.sha_json(fc.get("input") or {}), graph_hash=None,
                input_window_hash=pv.sha_json((fc.get("input") or {}).get("last_utc") or fc.get("input") or {}),
                cache_hit_training=False, result_source="LIVE_COMPUTATION")
        run.stage("Running inference", emit)
        # corridors the recorder never sampled (6 of the 12) are forecast from the persisted
        # observatory window instead — shorter history, same model, same units after conversion
        try:
            if not dhaka:
                raise LookupError("no observatory for this city")
            from backend.app.live import observatory as obs_mod
            from pipeline.forecasting.adapters.registry import forecast as run_forecast
            cd = obs_mod.observatory.city_data(city)
            if cd.shape[0] >= 8:
                import numpy as np
                from backend.app.live.google_routes import classify
                fo = (run_forecast(cd, HORIZONS) or {}).get("forecast")
                if fo:
                    last = np.asarray(cd.values)[-1]
                    for hh in HORIZONS:
                        vals = fo["values"].get(hh) or fo["values"].get(str(hh)) or []
                        for cid, v in zip(fo["node_ids"], vals):
                            if cid in pred[hh] and pred[hh][cid] is not None:
                                continue
                            if v is None or (isinstance(v, float) and math.isnan(v)):
                                continue
                            # the observatory forecasts a SPEED (m/s); the level is the class the
                            # live/free-flow ratio would fall in, using the corridor's static speed
                            live_c = next((c for c in corr.get("corridors", []) if c["id"] == cid), None)
                            if not live_c or not live_c.get("static_duration_s") or not live_c.get("distance_m"):
                                continue
                            free_ms = float(live_c["distance_m"]) / float(live_c["static_duration_s"])
                            ratio = free_ms / max(float(v), 0.1)
                            lvl = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5}.get(classify(ratio, 1.0), 0.0)
                            pred[hh][cid] = lvl
                            if cid not in observed:
                                now_ratio = free_ms / max(float(last[fo["node_ids"].index(cid)]), 0.1) if last[fo["node_ids"].index(cid)] == last[fo["node_ids"].index(cid)] else 1.0
                                observed[cid] = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5}.get(classify(now_ratio, 1.0), 0.0)
        except Exception as exc:                        # noqa: BLE001 - the recorded forecast still stands
            emit(observatory_note=f"observatory forecast unavailable: {type(exc).__name__}: {exc}")
        acc = _accuracy(f.get("model", ""))

        run.set(raw_prediction_hash=pv.sha_json({str(k): {kk: (None if vv is None or vv != vv else round(float(vv), 4)) for kk, vv in v.items()} for k, v in pred.items()}),
                raw_prediction_first10=[None if v is None or v != v else round(float(v), 3) for v in list(pred.get(HORIZONS[0], {}).values())[:10]],
                # the full raw prediction (corridor -> value per horizon) is kept with the run so the route
                # optimizer prices edges from THIS forecast, never from a recomputation on a later window
                raw_prediction={str(k): {kk: (None if vv is None or vv != vv else round(float(vv), 4)) for kk, vv in v.items()} for k, v in pred.items()},
                forecast_unit=f.get("unit") if f else None)
        run.stage("Evaluating routes", emit)
        if dhaka:
            axes = _corridor_polylines(corr)
        elif forecastable:
            axes = {c["id"]: [tuple(pt) for sgm in (c.get("segments") or []) for pt in (sgm.get("coordinates") or [])]
                    for c in corr.get("corridors", []) if _usable(c)}
            axes = {k: v for k, v in axes.items() if len(v) >= 2}
        else:
            axes = {}
        live_by_id = {c["id"]: c for c in corr.get("corridors", [])}
        cards = []
        for i, r in enumerate(routes["routes"][:3]):
            pts = [tuple(pt) for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])]
            touched = []
            for cid, poly in axes.items():
                if runs_along(pts, poly):
                    touched.append(cid)
            per_h = {}
            for hh in HORIZONS:
                pairs = [(float(pred[hh][cid]), observed.get(cid))
                         for cid in touched if pred[hh].get(cid) is not None
                         and not math.isnan(float(pred[hh][cid]))]
                if pairs:
                    # the forecast moves the CURRENT ETA by the ratio of the predicted to the
                    # observed congestion band on the worst corridor the route runs along
                    lvl_pred = max(0.0, min(3.0, max(x for x, _ in pairs)))
                    lvl_now = max(0.0, min(3.0, max(float(o) if o is not None else x for x, o in pairs)))
                    factor = max(0.7, min(3.0, multiplier(lvl_pred) / multiplier(lvl_now)))
                    eta, level, covered = float(r["duration_s"]) * factor, lvl_pred, True
                else:
                    eta, level, covered = float(r["duration_s"]), None, False
                per_h[hh] = {"eta_s": round(eta), "level": None if level is None else round(level, 2),
                             "risk": ("—" if level is None else "HIGH" if level >= 2 else "MEDIUM" if level >= 1 else "LOW"),
                             "covered": covered}
            cards.append({"key": "ABC"[i], "index": i, "eta_now_s": r["duration_s"],
                          "static_s": r.get("static_duration_s"), "distance_m": r.get("distance_m"),
                          "category_now": r.get("category"), "corridors": touched,
                          "forecast": per_h, "segments": r.get("segments") or []})
        best_now = min(cards, key=lambda c: c["eta_now_s"])
        best_pred = min(cards, key=lambda c: c["forecast"][h]["eta_s"])
        saving = best_now["forecast"][h]["eta_s"] - best_pred["forecast"][h]["eta_s"]
        for c in cards:
            c["recommended"] = c["key"] == best_pred["key"]
            c["status"] = ("RECOMMENDED" if c["key"] == best_pred["key"] else
                           "AVOID" if c["forecast"][h]["risk"] == "HIGH" else "ACCEPTABLE")
        covered_any = any(c["forecast"][h]["covered"] for c in cards)
        if not forecastable:
            reason = (f"no forecast history for {city} yet — the fastest live route stands; "
                      f"start observing {city} to get one, or simulate this area to test rerouting")
        elif not covered_any:
            reason = "no forecast-covered corridor on these routes; the fastest route now stands"
        elif best_pred["key"] == best_now["key"]:
            reason = (f"the forecast keeps route {best_pred['key']} fastest at +{h} min "
                      f"({best_pred['forecast'][h]['risk'].lower()} congestion risk)")
        else:
            reason = (f"route {best_now['key']} is fastest now but its corridor is forecast "
                      f"{best_now['forecast'][h]['risk']} at +{h} min; route {best_pred['key']} "
                      f"saves about {round(saving / 60)} min")
        a_h = (acc.get(h) or {}) if dhaka else {}       # the backtest is Dhaka's; never borrowed
        cur_speed = (best_now["distance_m"] / best_now["eta_now_s"] * 3.6) if best_now.get("distance_m") else None
        layers = {"now": [{"id": c["id"], "level": c.get("level"), "category": c.get("category"),
                           "segments": c.get("segments") or []} for c in corr.get("corridors", []) if _usable(c)]
                  if (dhaka or forecastable) else []}
        for hh in HORIZONS:
            layers[str(hh)] = [{"id": cid, "level": (None if pred[hh].get(cid) is None else round(float(pred[hh][cid]), 2)),
                                "segments": (live_by_id.get(cid) or {}).get("segments") or []}
                               for cid in axes if cid in pred[hh]]
        lats = [pt[0] for c in cards for pt in [tuple(q) for sgm in c["segments"] for q in (sgm.get("coordinates") or [])]]
        lngs = [pt[1] for c in cards for pt in [tuple(q) for sgm in c["segments"] for q in (sgm.get("coordinates") or [])]]
        pad = 0.006
        bbox = [min(lats) - pad, min(lngs) - pad, max(lats) + pad, max(lngs) + pad] if lats else None
        result = {
            "city": city, "is_dhaka": dhaka, "forecastable": forecastable, "observe": observe, "bbox": bbox,
            "origin": o, "destination": d, "departure": dep, "horizon_min": h,
            "requested_horizon_min": horizon,
            "current": {"eta_s": best_now["eta_now_s"], "route": best_now["key"],
                        "speed_kmh": round(cur_speed, 1) if cur_speed else None,
                        "congestion": best_now["category_now"], "distance_m": best_now["distance_m"]},
            "forecast": {"eta_s": best_now["forecast"][h]["eta_s"], "risk": best_now["forecast"][h]["risk"],
                         "covered": best_now["forecast"][h]["covered"],
                         "confidence": (f"{a_h['class_accuracy'] * 100:.0f} % class accuracy at +{h} min "
                                        f"on this city's recorded data" if a_h else
                                        (f"{observe['steps_have']} live samples so far — not yet scored" if forecastable
                                         else f"no observed corridors in {city} yet")),
                         "class_accuracy": a_h.get("class_accuracy"), "model": f.get("model"),
                         "checkpoint": f.get("checkpoint"), "input_steps": f.get("input_window_steps"),
                         "observed_levels": observed},
            "decision": {"recommended": best_pred["key"], "saving_s": max(0, saving), "reason": reason,
                         "basis": "forecast-derived future edge costs on the observed corridors"},
            "routes": cards, "layers": layers, "retrieved_at": routes.get("retrieved_at"),
            "source": {"traffic": ("Google Routes API, TRAFFIC_AWARE_OPTIMAL (live)" if routes.get("source") == "google_routes" else f"local SUMO router on the frozen Dhaka OSM network · {traffic_basis}"),
                       "traffic_basis": traffic_basis, "is_live": routes.get("source") == "google_routes", "routing": routes.get("source"), "forecast": fc.get("input", {})},
        }
        run.stage("Preparing result", emit)
        run.set(postprocessed_prediction_hash=pv.sha_json([c["forecast"] for c in cards]), recommended=best_pred["key"])
        rec = run.finish("done")
        result.update(run_id=job, result_source="LIVE_COMPUTATION", cache_hit_training=False, inference_recomputed=True,
                      provenance=run.summary(), stages=rec["stages"],
                      forecast_decision={**product["forecast"], "model_used": f.get("model") if f else None}, routing_policy=product["routing"])
        emit(stage="done", step=4, status="done", result=result)
    except (Exception, SystemExit) as exc:          # noqa: BLE001 - the page shows the real reason; a pipeline SystemExit must not leave the job "running" forever
        try:
            run.finish("failed", f"{type(exc).__name__}: {exc}")
        except Exception:                               # noqa: BLE001 - provenance never masks the real error
            pass
        emit(stage="failed", status="failed", error=f"{type(exc).__name__}: {exc}")


def start(payload: dict) -> str:
    job = "an_" + uuid.uuid4().hex[:8]
    with _LOCK:
        _JOBS[job] = {"job": job, "status": "running", "stage": "Fetching traffic", "step": 0,
                      "started_utc": datetime.now(timezone.utc).isoformat(), "request": payload}
    threading.Thread(target=_run, args=(job, payload), name=job, daemon=True).start()
    return job


def status(job: str) -> dict:
    with _LOCK:
        return dict(_JOBS.get(job) or {"job": job, "status": "unknown"})


def models_for_city(city: str) -> list[dict]:
    """Which forecast models can serve THIS city's corridor history right now, with reasons —
    the registry's own gates, so the menu never offers a model that would refuse."""
    from pipeline.forecasting.adapters.registry import available_for
    from backend.app.live import observatory as obs_mod
    cid = city_id_for(city)
    out = [{"model": "auto", "label": "Automatic (best available)", "available": True, "reasons": []}]
    scope = city if str(city).startswith("user:") else cid if str(cid or "").startswith("user:") else None
    if scope:                                          # an uploaded dataset: the registry's own list for that data (trained, pretrained, baselines)
        from backend.app.forecasting import model_registry
        try:
            reg = model_registry.registry(scope)
        except (Exception, SystemExit) as exc:         # noqa: BLE001
            return out + [{"model": "GWNet", "label": "GWNet", "available": False, "reasons": [f"registry unavailable: {exc}"[:200]]}]
        for g in reg.get("groups", []):
            for e in g.get("items", []):
                if e.get("model") == "auto":
                    continue
                out.append({"model": e["model"], "label": e.get("label") or e["model"], "available": bool(e.get("can_forecast")),
                            "reasons": [x for x in [e.get("reason") or e.get("trust_message")] if x][:2], "status": e.get("status"), "trust": e.get("trust"),
                            "trained": bool(e.get("trained")), "test_skill": e.get("test_skill"), "group": g.get("key")})
        return out
    try:
        if is_dhaka(city):
            from pipeline.routing.forecast_to_costs import recorded_city_data
            cd = recorded_city_data("dhaka")
            cd = cd[0] if isinstance(cd, tuple) else cd
        elif cid and obs_mod.observatory.readiness(cid)["steps_have"] >= 1:
            cd = obs_mod.observatory.city_data(cid)
        else:
            return out + [{"model": m, "label": m, "available": False, "reasons": ["no history for this city yet"]}
                          for m in ("OpenCity-plus", "Chronos-Bolt", "historical_average", "persistence")]
        for m in available_for(cd):
            if m["model"].split("/")[0] in ("STAEformer", "GWNet", "STID"):
                continue                                # benchmark-trained; not for a city's corridors
            out.append({"model": m["model"], "label": m["model"], "available": m["available"], "reasons": m.get("reasons", [])[:2]})
    except (Exception, SystemExit) as exc:              # noqa: BLE001 - the pipeline raises SystemExit for a missing recorded series
        out.append({"model": "Chronos-Bolt", "label": "Chronos-Bolt", "available": False, "reasons": [f"no corridor history available: {exc}"[:200]]})
    return out
