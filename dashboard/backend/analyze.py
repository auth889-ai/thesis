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

import config
import corridors as cz

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
def is_dhaka(city: str) -> bool:
    return re.sub(r"[^a-z]", "", (city or "").lower()) in ("dhaka", "dhakabangladesh", "dhakar")


def resolve_place(text: str, city: str = "dhaka") -> dict:
    """'lat, lng' | a known Dhaka place | free text via OpenStreetMap's geocoder, inside the
    named city. Never silent: an unknown place is an error the page shows."""
    t = (text or "").strip()
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", t)
    if m:
        return {"lat": float(m.group(1)), "lng": float(m.group(2)), "label": t, "source": "coordinates"}
    key = re.sub(r"[^a-z0-9]", "", t.lower())
    if is_dhaka(city):
        for name, (lat, lng) in cz.PLACES.items():
            if key == re.sub(r"[^a-z0-9]", "", name.lower()):
                return {"lat": lat, "lng": lng, "label": name, "source": "known place"}
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"q": f"{t}, {city}", "format": "json", "limit": 1})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}",
                                 headers={"User-Agent": "dhakaflow/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        hits = json.loads(r.read().decode())
    if not hits:
        raise ValueError(f"could not find '{t}'")
    return {"lat": float(hits[0]["lat"]), "lng": float(hits[0]["lon"]),
            "label": hits[0].get("display_name", t).split(",")[0], "source": "OpenStreetMap geocoder"}


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

        emit(stage="Fetching traffic", step=1)
        o = resolve_place(p.get("origin") or "farmgate", city)
        d = resolve_place(p.get("destination") or "shahbagh", city)
        from live import service
        routes = service.routes((o["lat"], o["lng"]), (d["lat"], d["lng"]))
        corr = service.corridors()
        if not routes.get("is_live") or not routes.get("routes"):
            raise RuntimeError(f"live routing unavailable: {routes.get('request_status')}")

        emit(stage="Running forecast", step=2)
        dhaka = is_dhaka(city)
        if dhaka:
            from pipeline.routing.forecast_to_costs import recorded_forecast
            fc = recorded_forecast("dhaka", HORIZONS, None, "latest")
        else:
            fc = {"forecast": None, "observed": {}, "input": {}}       # no observed corridors here
        f = fc.get("forecast") or {}
        pred = {hh: dict(zip(f.get("node_ids", []), f["values"].get(hh) or f["values"].get(str(hh)) or []))
                for hh in HORIZONS} if f else {hh: {} for hh in HORIZONS}
        observed = dict((fc.get("observed") or {}).get("levels") or {})
        # corridors the recorder never sampled (6 of the 12) are forecast from the persisted
        # observatory window instead — shorter history, same model, same units after conversion
        try:
            if not dhaka:
                raise LookupError("no observatory for this city")
            import observatory as obs_mod
            from pipeline.forecasting.adapters.registry import forecast as run_forecast
            cd = obs_mod.observatory.city_data(city)
            if cd.shape[0] >= 8:
                import numpy as np
                from live import classify
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

        emit(stage="Evaluating alternatives", step=3)
        axes = _corridor_polylines(corr) if dhaka else {}
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
        if not dhaka:
            reason = (f"no forecast history for {city} yet — the fastest live route stands; "
                      f"simulate this area to test rerouting")
        elif not covered_any:
            reason = "no forecast-covered corridor on these routes; the fastest route now stands"
        elif best_pred["key"] == best_now["key"]:
            reason = (f"the forecast keeps route {best_pred['key']} fastest at +{h} min "
                      f"({best_pred['forecast'][h]['risk'].lower()} congestion risk)")
        else:
            reason = (f"route {best_now['key']} is fastest now but its corridor is forecast "
                      f"{best_now['forecast'][h]['risk']} at +{h} min; route {best_pred['key']} "
                      f"saves about {round(saving / 60)} min")
        a_h = acc.get(h) or {}
        cur_speed = (best_now["distance_m"] / best_now["eta_now_s"] * 3.6) if best_now.get("distance_m") else None
        layers = {"now": [{"id": c["id"], "level": None, "category": c.get("category"),
                           "segments": c.get("segments") or []} for c in corr.get("corridors", []) if c.get("is_live")]}
        for hh in HORIZONS:
            layers[str(hh)] = [{"id": cid, "level": (None if pred[hh].get(cid) is None else round(float(pred[hh][cid]), 2)),
                                "segments": (live_by_id.get(cid) or {}).get("segments") or []}
                               for cid in axes if cid in pred[hh]]
        lats = [pt[0] for c in cards for pt in [tuple(q) for sgm in c["segments"] for q in (sgm.get("coordinates") or [])]]
        lngs = [pt[1] for c in cards for pt in [tuple(q) for sgm in c["segments"] for q in (sgm.get("coordinates") or [])]]
        pad = 0.006
        bbox = [min(lats) - pad, min(lngs) - pad, max(lats) + pad, max(lngs) + pad] if lats else None
        result = {
            "city": city, "is_dhaka": dhaka, "bbox": bbox,
            "origin": o, "destination": d, "departure": dep, "horizon_min": h,
            "requested_horizon_min": horizon,
            "current": {"eta_s": best_now["eta_now_s"], "route": best_now["key"],
                        "speed_kmh": round(cur_speed, 1) if cur_speed else None,
                        "congestion": best_now["category_now"], "distance_m": best_now["distance_m"]},
            "forecast": {"eta_s": best_now["forecast"][h]["eta_s"], "risk": best_now["forecast"][h]["risk"],
                         "covered": best_now["forecast"][h]["covered"],
                         "confidence": (f"{a_h['class_accuracy'] * 100:.0f} % class accuracy at +{h} min "
                                        f"on this city's recorded data" if a_h else
                                        ("not yet measured" if dhaka else f"no observed corridors in {city} yet")),
                         "class_accuracy": a_h.get("class_accuracy"), "model": f.get("model"),
                         "checkpoint": f.get("checkpoint"), "input_steps": f.get("input_window_steps"),
                         "observed_levels": observed},
            "decision": {"recommended": best_pred["key"], "saving_s": max(0, saving), "reason": reason,
                         "basis": "forecast-derived future edge costs on the observed corridors"},
            "routes": cards, "layers": layers, "retrieved_at": routes.get("retrieved_at"),
            "source": {"traffic": "Google Routes API, TRAFFIC_AWARE_OPTIMAL", "forecast": fc.get("input", {})},
        }
        emit(stage="done", step=4, status="done", result=result)
    except Exception as exc:                        # noqa: BLE001 - the page shows the real reason
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
