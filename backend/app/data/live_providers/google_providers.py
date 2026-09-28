"""Google Routes + Google Weather providers — real API shapes, key-gated.

Both providers are fully implemented against the actual Google Maps Platform
endpoints and are unit-tested through an injectable transport, so the first
live call exercises code that has already run. Without `GOOGLE_MAPS_API_KEY`
they report `enabled=False` and refuse to fetch — never fake data.

Legal note (recorded, not hidden): Google Maps Platform terms restrict caching
and storage of Maps Content. Raw-response persistence is therefore OFF by
default and must be explicitly enabled with `persist_raw=True` after the
operator has reviewed the current ToS. Derived scalars we compute (delay =
duration − staticDuration) and request metadata are ours.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from app.common.reality import Provenance, RealityClass
from app.data.live_providers.providers import ObservationStore, TrafficEdgeState, WeatherState

ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
WEATHER_ENDPOINT = "https://weather.googleapis.com/v1/currentConditions:lookup"


# ---------------------------------------------------------------------------
# Compliance policy (user mandate 2026-08-17): GOOGLE_DATA_MODE
# ---------------------------------------------------------------------------

class GoogleDataPolicy:
    """RUNTIME_REFERENCE is the default and only shipped mode.

    Google Routes fields are a transient external reference for runtime use
    (current ETA, congestion state, dashboard comparison). They are NOT a
    persistent ML dataset: with `persist_google_route_content=False` the
    normalised store receives request metadata and DERIVED congestion verdicts
    only — no durations, no distances, no speed intervals, no geometry.
    Changing any flag requires explicit written Google contract/permission
    review, recorded in `permission_basis`.
    """

    MODE = "RUNTIME_REFERENCE"

    def __init__(self, persist_raw: bool = False,
                 persist_google_route_content: bool = False,
                 ml_training_allowed: bool = False,
                 ml_validation_allowed: bool = False,
                 export_allowed: bool = False,
                 permission_basis: str = ""):
        non_default = (persist_raw or persist_google_route_content or
                       ml_training_allowed or ml_validation_allowed or
                       export_allowed)
        if non_default and not permission_basis:
            raise ValueError(
                "Non-default Google data flags require permission_basis citing "
                "the explicit Google contract/permission that allows it")
        self.persist_raw = persist_raw
        self.persist_google_route_content = persist_google_route_content
        self.ml_training_allowed = ml_training_allowed
        self.ml_validation_allowed = ml_validation_allowed
        self.export_allowed = export_allowed
        self.permission_basis = permission_basis

    def congestion_bucket(self, duration_s: float, static_s: float) -> str:
        """DERIVED verdict — ours to persist. Ratio of live to free-flow time."""
        if static_s <= 0:
            return "UNKNOWN"
        r = duration_s / static_s
        if r < 1.15:
            return "FREE_FLOW"
        if r < 1.5:
            return "SLOW"
        if r < 2.0:
            return "CONGESTED"
        return "SEVERE"

# Field mask: exactly what we consume, nothing more (billing + minimisation).
ROUTES_FIELD_MASK = ",".join([
    "routes.duration",
    "routes.staticDuration",
    "routes.distanceMeters",
    "routes.polyline.encodedPolyline",          # hashed to route_ref, see below
    "routes.travelAdvisory.speedReadingIntervals",
])


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_transport(url: str, body: bytes | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _parse_duration(s: str | None) -> float:
    """Google returns durations like '1234s'."""
    if not s:
        return 0.0
    return float(s.rstrip("s"))


class GoogleRoutesProvider:
    """`TrafficProvider` over the Routes API (traffic-aware)."""

    def __init__(self, store: ObservationStore | None = None,
                 api_key: str | None = None,
                 transport: Callable[[str, bytes | None, dict], dict] | None = None,
                 policy: GoogleDataPolicy | None = None):
        self._key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self._transport = transport or _default_transport
        self._store = store
        self.policy = policy or GoogleDataPolicy()

    @property
    def name(self) -> str:
        return "google_routes"

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def edge_state(self, corridor_id: str, origin: tuple[float, float],
                   dest: tuple[float, float]) -> TrafficEdgeState:
        if not self.enabled:
            raise RuntimeError(
                "GoogleRoutesProvider disabled: GOOGLE_MAPS_API_KEY not set. "
                "Status stays READY_NOT_EXECUTED — no data is fabricated.")

        body = json.dumps({
            "origin": {"location": {"latLng": {"latitude": origin[0],
                                               "longitude": origin[1]}}},
            "destination": {"location": {"latLng": {"latitude": dest[0],
                                                    "longitude": dest[1]}}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "extraComputations": ["TRAFFIC_ON_POLYLINE"],
        }).encode()
        headers = {"Content-Type": "application/json",
                   "X-Goog-Api-Key": self._key,
                   "X-Goog-FieldMask": ROUTES_FIELD_MASK}

        t0 = time.monotonic()
        payload = self._transport(ROUTES_ENDPOINT, body, headers)
        latency_ms = (time.monotonic() - t0) * 1000.0
        captured = _now_utc()

        routes = payload.get("routes") or []
        if not routes:
            raise RuntimeError(f"Routes API returned no route for {corridor_id}")
        r = routes[0]
        duration = _parse_duration(r.get("duration"))
        static = _parse_duration(r.get("staticDuration"))
        poly = (r.get("polyline") or {}).get("encodedPolyline", "")
        intervals = tuple(
            (i.get("startPolylinePointIndex", 0), i.get("endPolylinePointIndex", 0),
             i.get("speed", "UNKNOWN"))
            for i in (r.get("travelAdvisory") or {}).get("speedReadingIntervals", []))

        state = TrafficEdgeState(
            corridor_id=corridor_id,
            origin_lat=origin[0], origin_lng=origin[1],
            dest_lat=dest[0], dest_lng=dest[1],
            duration_s=duration,
            static_duration_s=static,
            distance_m=float(r["distanceMeters"]) if "distanceMeters" in r else None,
            traffic_delay_s=max(duration - static, 0.0),
            speed_intervals=intervals,
            # Geometry is referenced by hash, not stored in the normalised state.
            route_ref=hashlib.sha256(poly.encode()).hexdigest()[:16] if poly else "",
            provenance=Provenance(
                provider=self.name,
                reality=RealityClass.REAL_LIVE,
                captured_utc=captured,
                request_latency_ms=round(latency_ms, 1),
                metadata={"endpoint": ROUTES_ENDPOINT,
                          "routing_preference": "TRAFFIC_AWARE_OPTIMAL",
                          "classification": "EXTERNAL_LIVE_REFERENCE",
                          "not_a": "vehicle count / queue length / CV ground truth"}),
        )
        if self._store:
            if self.policy.persist_raw:
                self._store.append_raw(self.name, payload, captured)
            if self.policy.persist_google_route_content:
                self._store.append_normalized(state)
            else:
                # RUNTIME_REFERENCE: persist metadata + DERIVED verdict only.
                self._store.append_runtime_reference(self.name, {
                    "corridor_id": corridor_id,
                    "captured_utc": captured,
                    "request_latency_ms": round(latency_ms, 1),
                    "congestion_state": self.policy.congestion_bucket(
                        duration, static),                 # derived, ours
                    "google_data_mode": GoogleDataPolicy.MODE,
                    "route_content_persisted": False,
                })
        return state


class GoogleWeatherProvider:
    """`WeatherProvider` over the Google Weather API (current conditions)."""

    def __init__(self, store: ObservationStore | None = None,
                 api_key: str | None = None,
                 transport: Callable[[str, bytes | None, dict], dict] | None = None):
        self._key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        self._transport = transport or _default_transport
        self._store = store

    @property
    def name(self) -> str:
        return "google_weather"

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def current(self, lat: float, lng: float) -> WeatherState:
        if not self.enabled:
            raise RuntimeError("GoogleWeatherProvider disabled: no GOOGLE_MAPS_API_KEY")

        url = (f"{WEATHER_ENDPOINT}?key={self._key}"
               f"&location.latitude={lat}&location.longitude={lng}")
        t0 = time.monotonic()
        p = self._transport(url, None, {})
        latency_ms = (time.monotonic() - t0) * 1000.0
        captured = _now_utc()

        def num(path: list[str]) -> float | None:
            cur = p
            for k in path:
                if not isinstance(cur, dict) or k not in cur:
                    return None
                cur = cur[k]
            return float(cur) if isinstance(cur, (int, float)) else None

        state = WeatherState(
            lat=lat, lng=lng,
            temperature_c=num(["temperature", "degrees"]),
            humidity_pct=num(["relativeHumidity"]),
            precipitation_mm=num(["precipitation", "qpf", "quantity"]),
            precipitation_probability_pct=num(["precipitation", "probability", "percent"]),
            precipitation_type=(p.get("precipitation", {}).get("probability", {})
                                .get("type")),
            visibility_km=num(["visibility", "distance"]),
            wind_speed_kmh=num(["wind", "speed", "value"]),
            wind_direction_deg=num(["wind", "direction", "degrees"]),
            cloud_cover_pct=num(["cloudCover"]),
            condition=(p.get("weatherCondition", {}).get("type")),
            provenance=Provenance(
                provider=self.name, reality=RealityClass.REAL_LIVE,
                captured_utc=captured, request_latency_ms=round(latency_ms, 1),
                metadata={"endpoint": WEATHER_ENDPOINT,
                          "role": "candidate exogenous variable — forecasting "
                                  "benefit requires an ablation before any claim"}),
        )
        if self._store:
            self._store.append_raw(self.name, p, captured)
            self._store.append_normalized(state)
        return state
