"""Live traffic from the Google Routes API — the runtime half of the system.

    from live import service
    snapshot = service.corridors()          # all corridors, live
    one      = service.corridor("farmgate_to_shahbagh")
    routes   = service.routes(origin, dest, alternatives=True)

WHAT IS REQUESTED
    `computeRoutes` with `routingPreference: TRAFFIC_AWARE_OPTIMAL` and the extra computation
    `TRAFFIC_ON_POLYLINE`, under a field mask of exactly:

        routes.duration                              live, traffic-aware ETA
        routes.staticDuration                        the same route with no traffic
        routes.distanceMeters
        routes.polyline.encodedPolyline              geometry, decoded here for the map
        routes.travelAdvisory.speedReadingIntervals  per-segment NORMAL / SLOW / TRAFFIC_JAM

    The traffic penalty is ours, derived: duration − staticDuration.

SEGMENT COLOURS
    `speedReadingIntervals` gives Google's own three categories against polyline point ranges, so
    the map is coloured from the API's classification rather than a threshold we invented. Points
    no interval covers are `UNKNOWN` and are drawn neutral, not green — absence of a reading is not
    evidence of free flow.

CACHING AND STORAGE — deliberately narrow
    Google Maps Platform terms restrict storing Maps Content. Displaying it live is the intended
    use; keeping it is not. So route content lives in a process-memory dictionary with a short TTL
    (`TTL_S`) and is **never written to disk**. Nothing here appends to the recorder's store, which
    continues to persist only derived congestion verdicts (`GoogleDataPolicy.RUNTIME_REFERENCE`).
    Restart the server and the cache is gone, which is the intended behaviour.

FAILURE IS REPORTED, NEVER PAPERED OVER
    Every response carries `source`, `retrieved_at`, `is_live` and `request_status`. On a failed or
    unauthenticated call `is_live` is false and `request_status` says why (`NO_CREDENTIALS`,
    `HTTP_403`, `TIMEOUT`, ...). This module has no fallback to recorded data: substituting stored
    readings behind a "live" label is the one thing it must never do.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import corridors as _corridors
import credentials as _secrets

ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = ",".join([
    "routes.duration",
    "routes.staticDuration",
    "routes.distanceMeters",
    "routes.polyline.encodedPolyline",
    "routes.travelAdvisory.speedReadingIntervals",
    "routes.description",
])
TTL_S = 120.0          # in memory only; see the caching note above
TIMEOUT_S = 12.0

# Google's own categories, in the order the interface renders them.
CATEGORIES = ("NORMAL", "SLOW", "TRAFFIC_JAM")
COLOURS = {"NORMAL": "green", "SLOW": "yellow", "TRAFFIC_JAM": "red", "UNKNOWN": "grey"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_polyline(encoded: str) -> list[list[float]]:
    """Google's encoded polyline -> [[lat, lng], ...]. Standard algorithm, no dependency."""
    coords, i, lat, lng = [], 0, 0, 0
    while i < len(encoded):
        for is_lat in (True, False):
            shift, result = 0, 0
            while i < len(encoded):
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lng += delta
        coords.append([lat * 1e-5, lng * 1e-5])
    return coords


def _seconds(v) -> float | None:
    """Routes API durations arrive as '123s'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    return float(s[:-1]) if s.endswith("s") else float(s)


def _http(url: str, body: bytes, headers: dict) -> tuple[dict | None, str, int]:
    """Returns (payload, request_status, http_status). Never raises."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode()), "OK", r.status
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("status", "")
        except Exception:                                   # noqa: BLE001 - best effort only
            pass
        return None, f"HTTP_{e.code}" + (f"_{detail}" if detail else ""), e.code
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", "")
        return None, ("TIMEOUT" if "timed out" in str(reason).lower() else "NETWORK_ERROR"), 0
    except (TimeoutError, OSError):
        return None, "TIMEOUT", 0
    except json.JSONDecodeError:
        return None, "BAD_JSON", 0


def classify(duration_s: float | None, static_s: float | None) -> str:
    """Corridor-level category from the traffic penalty, when segment readings are absent.

    Bands are the ones the recorder has used since the start of the project, so a live verdict and
    a recorded one mean the same thing: ratio < 1.15 NORMAL, < 1.5 SLOW, else TRAFFIC_JAM.
    """
    if not duration_s or not static_s or static_s <= 0:
        return "UNKNOWN"
    ratio = duration_s / static_s
    return "NORMAL" if ratio < 1.15 else ("SLOW" if ratio < 1.5 else "TRAFFIC_JAM")


def _segments(points: list[list[float]], intervals: list[dict]) -> list[dict]:
    """Split the geometry into coloured runs using Google's own speed readings."""
    out = []
    for iv in intervals or []:
        a = int(iv.get("startPolylinePointIndex", 0))
        b = int(iv.get("endPolylinePointIndex", a))
        speed = iv.get("speed", "UNKNOWN")
        seg = points[a:b + 1]
        if len(seg) >= 2:
            out.append({"speed": speed, "colour": COLOURS.get(speed, "grey"), "coordinates": seg})
    if not out and len(points) >= 2:                 # no readings: neutral, never assumed clear
        out.append({"speed": "UNKNOWN", "colour": "grey", "coordinates": points})
    return out


def _route_record(r: dict) -> dict:
    duration = _seconds(r.get("duration"))
    static = _seconds(r.get("staticDuration"))
    points = decode_polyline((r.get("polyline") or {}).get("encodedPolyline", ""))
    intervals = (r.get("travelAdvisory") or {}).get("speedReadingIntervals", []) or []
    penalty = max((duration or 0) - (static or 0), 0.0) if duration and static else None
    counts = {c: 0 for c in CATEGORIES}
    for iv in intervals:
        s = iv.get("speed")
        if s in counts:
            counts[s] += 1
    return {
        "duration_s": duration,
        "static_duration_s": static,
        "traffic_penalty_s": penalty,
        "traffic_penalty_pct": (round(penalty / static * 100, 1)
                                if penalty is not None and static else None),
        "distance_m": float(r["distanceMeters"]) if r.get("distanceMeters") is not None else None,
        "category": classify(duration, static),
        "description": r.get("description", ""),
        "geometry": points,
        "segments": _segments(points, intervals),
        "speed_interval_counts": counts,
        "speed_intervals": [
            {"start": int(i.get("startPolylinePointIndex", 0)),
             "end": int(i.get("endPolylinePointIndex", 0)),
             "speed": i.get("speed", "UNKNOWN")} for i in intervals],
    }


class LiveService:
    """Talks to Google. Holds nothing on disk. Reports its own health honestly."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._calls = 0
        self._failures = 0
        self._last_status = "NOT_CALLED"
        self._last_ok_utc: str | None = None
        self._last_latency_ms: float | None = None

    # ---------------------------------------------------------------- health
    @property
    def configured(self) -> bool:
        return bool(_secrets.google_key())

    def health(self) -> dict:
        return {
            "google_routes": {
                "configured": self.configured,
                "fingerprint": _secrets.fingerprint(_secrets.google_key()),
                "calls": self._calls,
                "failures": self._failures,
                "last_request_status": self._last_status,
                "last_success_utc": self._last_ok_utc,
                "last_latency_ms": self._last_latency_ms,
                "routing_preference": "TRAFFIC_AWARE_OPTIMAL",
                "endpoint": ROUTES_ENDPOINT,
            },
            "here_traffic": {"configured": bool(_secrets.here_key()),
                             "note": "segment speed / jam factor / incidents when credentials exist"},
            "cache": {"entries": len(self._cache), "ttl_s": TTL_S,
                      "storage": "process memory only — route content is never written to disk"},
            "checked_at": _now(),
        }

    # ------------------------------------------------------------ the call
    def _compute(self, origin: tuple[float, float], dest: tuple[float, float],
                 alternatives: bool = False) -> tuple[list[dict], str, float | None]:
        key = _secrets.google_key()
        if not key:
            self._last_status = "NO_CREDENTIALS"
            return [], "NO_CREDENTIALS", None
        body = json.dumps({
            "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
            "destination": {"location": {"latLng": {"latitude": dest[0], "longitude": dest[1]}}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "computeAlternativeRoutes": bool(alternatives),
            "extraComputations": ["TRAFFIC_ON_POLYLINE"],
        }).encode()
        headers = {"Content-Type": "application/json",
                   "X-Goog-Api-Key": key,
                   "X-Goog-FieldMask": FIELD_MASK}
        t0 = time.monotonic()
        payload, status, _ = _http(ROUTES_ENDPOINT, body, headers)
        latency = round((time.monotonic() - t0) * 1000, 1)

        with self._lock:
            self._calls += 1
            self._last_status = status
            self._last_latency_ms = latency
            if status != "OK":
                self._failures += 1
            else:
                self._last_ok_utc = _now()

        if status != "OK" or not payload:
            return [], status, latency
        routes = payload.get("routes") or []
        if not routes:
            return [], "NO_ROUTE", latency
        return [_route_record(r) for r in routes], "OK", latency

    # --------------------------------------------------------------- public
    def corridor(self, corridor_id: str, force: bool = False) -> dict:
        c = _corridors.BY_ID.get(corridor_id)
        if not c:
            return {"error": "unknown_corridor", "id": corridor_id, "is_live": False,
                    "request_status": "UNKNOWN_CORRIDOR", "source": "google_routes",
                    "retrieved_at": _now()}
        now = time.monotonic()
        if not force:
            with self._lock:
                hit = self._cache.get(corridor_id)
            if hit and now - hit[0] < TTL_S:
                rec = dict(hit[1])
                rec["cache_age_s"] = round(now - hit[0], 1)
                return rec

        origin, dest = _corridors.coords(c)
        routes, status, latency = self._compute(origin, dest)
        base = _corridors.describe(c)
        rec = {
            **base,
            "source": "google_routes",
            "retrieved_at": _now(),
            "is_live": status == "OK",
            "request_status": status,
            "request_latency_ms": latency,
            "routing_preference": "TRAFFIC_AWARE_OPTIMAL",
            "cache_age_s": 0.0,
        }
        if status == "OK":
            rec.update(routes[0])
            with self._lock:
                self._cache[corridor_id] = (now, dict(rec))
        else:
            rec.update({"duration_s": None, "static_duration_s": None, "traffic_penalty_s": None,
                        "distance_m": None, "category": "UNAVAILABLE", "geometry": [],
                        "segments": [], "speed_intervals": []})
        return rec

    def corridor_from(self, cdef: dict, force: bool = False) -> dict:
        """A corridor given as a dict {id, name, road, origin{lat,lng}, destination{lat,lng}} —
        the shape city_corridors.derive() produces for any city."""
        cid = cdef["id"]
        now = time.monotonic()
        if not force:
            with self._lock:
                hit = self._cache.get(cid)
            if hit and now - hit[0] < TTL_S:
                rec = dict(hit[1]); rec["cache_age_s"] = round(now - hit[0], 1); return rec
        o, d = (cdef["origin"]["lat"], cdef["origin"]["lng"]), (cdef["destination"]["lat"], cdef["destination"]["lng"])
        routes, status, latency = self._compute(o, d)
        rec = {"id": cid, "name": cdef.get("name", cid), "road": cdef.get("road"),
               "origin": {"lat": o[0], "lng": o[1]}, "destination": {"lat": d[0], "lng": d[1]},
               "sumo_mapped": False, "source": "google_routes", "retrieved_at": _now(),
               "is_live": status == "OK", "request_status": status, "request_latency_ms": latency,
               "routing_preference": "TRAFFIC_AWARE_OPTIMAL", "cache_age_s": 0.0}
        if status == "OK":
            rec.update(routes[0])
            with self._lock:
                self._cache[cid] = (now, dict(rec))
        else:
            rec.update({"duration_s": None, "static_duration_s": None, "traffic_penalty_s": None,
                        "distance_m": None, "category": "UNAVAILABLE", "geometry": [],
                        "segments": [], "speed_intervals": []})
        return rec

    def corridors_for(self, city_id: str, force: bool = False) -> dict:
        """The live state of every observation corridor of a city — Dhaka's hand-picked twelve,
        or the list derived from the city's road graph."""
        if city_id in ("dhaka", "", None):
            return self.corridors(force=force)
        import city_corridors
        defs = city_corridors.load(city_id)
        items = [self.corridor_from(c, force=force) for c in defs]
        live = [i for i in items if i.get("is_live")]
        counts = {cat: sum(1 for i in live if i.get("category") == cat) for cat in CATEGORIES}
        return {"source": "google_routes", "retrieved_at": _now(), "is_live": bool(live),
                "request_status": "OK" if live else (items[0]["request_status"] if items else "NO_CORRIDORS"),
                "corridors": items, "city_id": city_id,
                "summary": {"total": len(items), "live": len(live), "unavailable": len(items) - len(live),
                            "by_category": counts}, "health": self.health()}

    def corridors(self, force: bool = False) -> dict:
        items = [self.corridor(c["id"], force=force) for c in _corridors.CORRIDORS]
        live = [i for i in items if i.get("is_live")]
        counts = {cat: sum(1 for i in live if i.get("category") == cat) for cat in CATEGORIES}
        return {
            "source": "google_routes",
            "retrieved_at": _now(),
            "is_live": bool(live),
            "request_status": "OK" if live else (items[0]["request_status"] if items else "NO_CORRIDORS"),
            "corridors": items,
            "summary": {"total": len(items), "live": len(live),
                        "unavailable": len(items) - len(live), "by_category": counts},
            "health": self.health(),
        }

    def routes(self, origin: tuple[float, float], dest: tuple[float, float]) -> dict:
        routes, status, latency = self._compute(origin, dest, alternatives=True)
        return {
            "source": "google_routes",
            "retrieved_at": _now(),
            "is_live": status == "OK",
            "request_status": status,
            "request_latency_ms": latency,
            "routing_preference": "TRAFFIC_AWARE_OPTIMAL",
            "origin": {"lat": origin[0], "lng": origin[1]},
            "destination": {"lat": dest[0], "lng": dest[1]},
            "routes": routes,
            "alternatives": max(len(routes) - 1, 0),
        }


service = LiveService()
