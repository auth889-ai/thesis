"""Amazon Location Service (Routes API) as the road provider — any city on earth; live traffic only where it returns any.

    service.routes((lat, lng), (lat, lng))             K routes with traffic-aware and free-flow times, geometry,
                                                        per-span congestion colouring, live incidents on the way
    service.corridor_from(cdef) / corridors()           the observation corridors, same record shape as the Google provider

Every response says what it is: `source: amazon_location`, `is_live`, `request_status`, and
`traffic_coverage` — true only when HERE reports a live or typical time different from the best case
somewhere on the route. Where a city has no traffic coverage (Dhaka in 2026) the times are road
routing at typical speeds and the record says so; the recorded corridor profile supplies congestion
there. Nothing is cached: every call is a fresh request, and the AWS key never leaves the server.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from core.common import credentials
from core.common.data import reference_corridors as _corridors

SOURCE = "amazon_location"
CATEGORIES = ("NORMAL", "SLOW", "TRAFFIC_JAM")
COLOURS = {"NORMAL": "green", "SLOW": "yellow", "TRAFFIC_JAM": "red", "UNKNOWN": "grey"}
SPAN_FEATURES = ["Duration", "BestCaseDuration", "TypicalDuration", "Distance", "Names", "Incidents"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify(duration_s: float | None, static_s: float | None) -> str:
    """The recorder's bands, so a live verdict and a recorded one mean the same: <1.15 NORMAL, <1.5 SLOW, else JAM."""
    if not duration_s or not static_s or static_s <= 0:
        return "UNKNOWN"
    ratio = duration_s / static_s
    return "NORMAL" if ratio < 1.15 else ("SLOW" if ratio < 1.5 else "TRAFFIC_JAM")


def _route_record(route: dict) -> dict:
    """One route: geometry as [lat, lng], per-span category from live vs best-case time, incidents on the way."""
    points, segments, incidents = [], [], []
    duration = static = typical = 0.0
    for leg in route.get("Legs", []):
        base = len(points)
        line = [[p[1], p[0]] for p in (leg.get("Geometry") or {}).get("LineString", [])]
        points += line
        spans = (leg.get("VehicleLegDetails") or {}).get("Spans", [])
        for i, sp in enumerate(spans):
            a = int(sp.get("GeometryOffset", 0)); b = int(spans[i + 1].get("GeometryOffset", len(line) - 1)) if i + 1 < len(spans) else len(line) - 1
            d, best, typ = float(sp.get("Duration", 0)), float(sp.get("BestCaseDuration", sp.get("Duration", 0))), float(sp.get("TypicalDuration", sp.get("Duration", 0)))
            duration += d; static += best; typical += typ
            cat = classify(d, best) if best else "UNKNOWN"
            seg = line[a:b + 1]
            if len(seg) >= 2:
                if segments and segments[-1]["speed"] == cat and segments[-1]["_leg"] == base:
                    segments[-1]["coordinates"] += seg[1:]
                else:
                    segments.append({"speed": cat, "colour": COLOURS[cat], "coordinates": list(seg), "_leg": base})
        # span Incidents are indexes into the leg's incident list; the leg list carries the details
        for inc in (leg.get("VehicleLegDetails") or {}).get("Incidents", []) or []:
            if isinstance(inc, dict):
                incidents.append({"type": inc.get("Type"), "severity": inc.get("Severity"), "description": inc.get("Description"), "start_time": str(inc.get("StartTime") or ""), "end_time": str(inc.get("EndTime") or "")})
    summary = route.get("Summary") or {}
    duration = float(summary.get("Duration", duration)) or duration
    static = static or duration
    for s in segments:
        s.pop("_leg", None)
    if not segments and len(points) >= 2:
        segments.append({"speed": "UNKNOWN", "colour": "grey", "coordinates": points})
    penalty = max(duration - static, 0.0)
    return {"duration_s": round(duration), "static_duration_s": round(static), "typical_duration_s": round(typical) if typical else None,
            "traffic_penalty_s": round(penalty), "traffic_penalty_pct": round(penalty / static * 100, 1) if static else None,
            "distance_m": float(summary.get("Distance", 0.0)), "category": classify(duration, static), "description": "",
            "geometry": points, "segments": segments, "speed_interval_counts": {c: sum(1 for s in segments if s["speed"] == c) for c in CATEGORIES},
            "speed_intervals": [], "incidents": incidents,
            "traffic_coverage": any(abs(float(sp.get("Duration", 0)) - float(sp.get("BestCaseDuration", sp.get("Duration", 0)))) > 0.5 or abs(float(sp.get("TypicalDuration", sp.get("Duration", 0))) - float(sp.get("Duration", 0))) > 0.5
                                    for leg in route.get("Legs", []) for sp in (leg.get("VehicleLegDetails") or {}).get("Spans", []))}


def preference(traffic_returned: bool) -> str:
    """How a result is described: the provider returned traffic for it, or only a free-flow time (Dhaka, checked 2026-10-04:
    identical durations with traffic on, off, at peak and a week ahead; evidence/audit_2026-10-05/)."""
    return "traffic-aware (Amazon Location)" if traffic_returned else "free-flow estimate (Amazon Location returned no traffic here)"


class AmazonLocation:
    source = SOURCE

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = self._failures = 0
        self._last_status: str | None = None
        self._last_latency_ms: float | None = None
        self._last_ok_utc: str | None = None

    @property
    def configured(self) -> bool:
        return bool(credentials.load("AWS_ACCESS_KEY_ID") and credentials.load("AWS_SECRET_ACCESS_KEY"))

    @property
    def region(self) -> str:
        return credentials.load("AWS_LOCATION_REGION") or credentials.load("BEDROCK_REGION") or credentials.load("AWS_REGION") or "us-west-2"

    def _client(self):
        import boto3
        return boto3.client("geo-routes", region_name=self.region, aws_access_key_id=credentials.load("AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=credentials.load("AWS_SECRET_ACCESS_KEY"), aws_session_token=credentials.load("AWS_SESSION_TOKEN") or None)

    def health(self) -> dict:
        with self._lock:
            return {"provider": SOURCE, "configured": self.configured, "region": self.region, "calls": self._calls, "failures": self._failures,
                    "last_request_status": self._last_status, "last_latency_ms": self._last_latency_ms, "last_ok_utc": self._last_ok_utc}

    def _compute(self, origin: tuple[float, float], dest: tuple[float, float], alternatives: bool = True, departure: str | None = None) -> tuple[list[dict], str, float | None]:
        if not self.configured:
            self._last_status = "NO_CREDENTIALS"
            return [], "NO_CREDENTIALS", None
        kw: dict = {"Origin": [origin[1], origin[0]], "Destination": [dest[1], dest[0]], "TravelMode": "Car", "Traffic": {"Usage": "UseTrafficData"},
                    "LegGeometryFormat": "Simple", "SpanAdditionalFeatures": SPAN_FEATURES, "MaxAlternatives": 2 if alternatives else 0}
        if departure:
            kw["DepartureTime"] = departure
        else:
            kw["DepartNow"] = True
        t0 = time.monotonic()
        try:
            payload = self._client().calculate_routes(**kw)
            status = "OK" if payload.get("Routes") else "NO_ROUTE"
        except Exception as exc:                            # noqa: BLE001 - the status carries the reason, never a key
            payload, status = None, f"ERROR_{type(exc).__name__}"
        latency = round((time.monotonic() - t0) * 1000, 1)
        with self._lock:
            self._calls += 1; self._last_status = status; self._last_latency_ms = latency
            if status == "OK":
                self._last_ok_utc = _now()
            else:
                self._failures += 1
        if status != "OK":
            return [], status, latency
        return [_route_record(r) for r in payload["Routes"]], "OK", latency

    def routes(self, origin: tuple[float, float], dest: tuple[float, float], departure: str | None = None) -> dict:
        routes, status, latency = self._compute(origin, dest, alternatives=True, departure=departure)
        covered = any(r.get("traffic_coverage") for r in routes)
        return {"source": SOURCE, "retrieved_at": _now(), "answered": status == "OK", "is_live": status == "OK" and covered, "request_status": status, "request_latency_ms": latency,
                "routing_preference": preference(covered), "traffic_coverage": covered,
                "origin": {"lat": origin[0], "lng": origin[1]}, "destination": {"lat": dest[0], "lng": dest[1]}, "routes": routes, "alternatives": max(len(routes) - 1, 0)}

    def corridor_from(self, cdef: dict) -> dict:
        o, d = (cdef["origin"]["lat"], cdef["origin"]["lng"]), (cdef["destination"]["lat"], cdef["destination"]["lng"])
        routes, status, latency = self._compute(o, d, alternatives=False)
        rec = {"id": cdef["id"], "name": cdef.get("name", cdef["id"]), "road": cdef.get("road"), "origin": {"lat": o[0], "lng": o[1]}, "destination": {"lat": d[0], "lng": d[1]},
               "sumo_mapped": cdef.get("sumo_mapped", False), "source": SOURCE, "retrieved_at": _now(), "answered": status == "OK", "request_status": status,
               "request_latency_ms": latency, "cache_age_s": 0.0}
        rec.update(routes[0] if status == "OK" else {"duration_s": None, "static_duration_s": None, "traffic_penalty_s": None, "distance_m": None, "category": "UNAVAILABLE", "geometry": [], "segments": [], "speed_intervals": [], "traffic_coverage": False})
        rec["is_live"] = rec["answered"] and bool(rec.get("traffic_coverage"))       # a free-flow time is an answer, not a live reading
        rec["routing_preference"] = preference(bool(rec.get("traffic_coverage")))
        return rec

    def corridor(self, corridor_id: str, force: bool = False) -> dict:
        c = next((x for x in _corridors.CORRIDORS if x["id"] == corridor_id), None)
        if not c:
            return {"id": corridor_id, "answered": False, "is_live": False, "request_status": "UNKNOWN_CORRIDOR", "source": SOURCE, "retrieved_at": _now()}
        return self.corridor_from(_corridors.describe(c))

    def _bundle(self, defs: list[dict], city_id: str | None) -> dict:
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(defs)))) as pool:      # one fresh request per corridor, in parallel
            items = list(pool.map(self.corridor_from, defs))
        answered, live = [i for i in items if i.get("answered")], [i for i in items if i.get("is_live")]
        return {"source": SOURCE, "retrieved_at": _now(), "answered": bool(answered), "is_live": bool(live), "request_status": "OK" if answered else (items[0]["request_status"] if items else "NO_CORRIDORS"),
                "traffic_coverage": bool(live), "corridors": items, "city_id": city_id,
                "summary": {"total": len(items), "answered": len(answered), "live": len(live), "unavailable": len(items) - len(answered), "by_category": {c: sum(1 for i in answered if i.get("category") == c) for c in CATEGORIES}}, "health": self.health()}

    def corridors(self, force: bool = False) -> dict:
        return self._bundle([_corridors.describe(c) for c in _corridors.CORRIDORS], "dhaka")

    def corridors_for(self, city_id: str, force: bool = False) -> dict:
        if city_id in ("dhaka", "", None):
            return self.corridors()
        from core.common.data import city_corridors
        return self._bundle(city_corridors.load(city_id), city_id)


service = AmazonLocation()
