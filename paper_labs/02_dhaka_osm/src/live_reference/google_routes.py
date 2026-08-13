"""GoogleRoutesReference — LiveTrafficReference provider for Google Routes API.

Conforms structurally to ``dhakaflow.common.LiveTrafficReference``.

Semantics (verified in LITERATURE_SELECTION_GATE.md §C1):
  - ``computeRoutes`` with ``routingPreference=TRAFFIC_AWARE`` (live conditions)
    or ``TRAFFIC_AWARE_OPTIMAL`` (higher accuracy, higher latency); both return
    ``duration`` (traffic-aware) and ``staticDuration`` (free-flow-ish).
  - A field mask is REQUIRED; we request only duration/staticDuration/distance.

Data policy (user DECISION 1, conservative — enforced here, not just in docs):
  - Responses are held in memory only; this module NEVER writes durations,
    distances, polylines, or any other Google Maps Content to disk.
  - ``LiveRouteObservation.persistable_metadata()`` is the only thing callers
    may record (status, preference, timestamp).
  - Polylines are not requested at all (field mask) — nothing to leak onto maps.

Disabled path: constructing without ``GOOGLE_MAPS_API_KEY`` in the environment
yields ``enabled=False``; every query returns ``status="DISABLED_NO_KEY"`` and
the lab records ``LIVE_REFERENCE = READY_NOT_EXECUTED``.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root

from dhakaflow.common.live_reference import (  # noqa: E402
    LiveRouteObservation, LiveRouteRequest)

_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
#: only non-Content-bearing scalar fields; deliberately NO polyline
_FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters"


def _parse_duration(s: str | None) -> float | None:
    if not s:
        return None
    return float(s.rstrip("s"))                     # API returns e.g. "1234s"


class GoogleRoutesReference:
    """Live reference provider; safe to construct with no key (disabled mode)."""

    def __init__(self, api_key: str | None = None,
                 transport: Callable[[dict, dict], dict] | None = None) -> None:
        self._key = api_key if api_key is not None else os.environ.get("GOOGLE_MAPS_API_KEY")
        self._transport = transport                  # tests inject a mock here

    @property
    def provider(self) -> str:
        return "google_routes_v2"

    @property
    def enabled(self) -> bool:
        return bool(self._key) or self._transport is not None

    def _http_transport(self, body: dict, headers: dict) -> dict:
        req = urllib.request.Request(
            _ENDPOINT, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    def travel_time(self, req: LiveRouteRequest) -> LiveRouteObservation:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not self.enabled:
            return LiveRouteObservation(request=req, provider=self.provider,
                                        status="DISABLED_NO_KEY", requested_at_utc=now)
        body = {
            "origin": {"location": {"latLng": {
                "latitude": req.origin_lat, "longitude": req.origin_lon}}},
            "destination": {"location": {"latLng": {
                "latitude": req.dest_lat, "longitude": req.dest_lon}}},
            "travelMode": "DRIVE",
            "routingPreference": req.routing_preference,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._key or "",
            "X-Goog-FieldMask": _FIELD_MASK,
        }
        transport = self._transport or self._http_transport
        try:
            payload = transport(body, headers)
        except Exception as exc:                      # noqa: BLE001 - reported in status
            return LiveRouteObservation(request=req, provider=self.provider,
                                        status=f"ERROR:{type(exc).__name__}",
                                        requested_at_utc=now,
                                        diagnostics={"detail": str(exc)[:200]})
        routes = payload.get("routes") or []
        if not routes:
            return LiveRouteObservation(request=req, provider=self.provider,
                                        status="ERROR:NO_ROUTE", requested_at_utc=now)
        r0 = routes[0]
        return LiveRouteObservation(
            request=req, provider=self.provider, status="OK", requested_at_utc=now,
            duration_s=_parse_duration(r0.get("duration")),
            static_duration_s=_parse_duration(r0.get("staticDuration")),
            distance_m=float(r0["distanceMeters"]) if "distanceMeters" in r0 else None,
        )


def ephemeral_sanity_check(reference: GoogleRoutesReference,
                           od_lonlat_pairs: list[tuple[tuple[float, float], tuple[float, float]]],
                           sumo_route_lengths_m: list[float | None]) -> dict:
    """Optional in-memory sanity test (DECISION 1). Returns ONLY derived booleans.

    Compares provider route distance against SUMO shortest-path distance as an
    order-of-magnitude plausibility band (factor 0.5–2.0). No provider values
    are included in the returned dict — only verdicts and request metadata.
    """
    verdicts, metadata = [], []
    for i, ((olon, olat), (dlon, dlat)) in enumerate(od_lonlat_pairs):
        obs = reference.travel_time(LiveRouteRequest(
            origin_lat=olat, origin_lon=olon, dest_lat=dlat, dest_lon=dlon,
            routing_preference="TRAFFIC_AWARE", label=f"OD{i}"))
        metadata.append(obs.persistable_metadata())
        if not obs.ok:
            verdicts.append(None)
            continue
        ours = sumo_route_lengths_m[i] if i < len(sumo_route_lengths_m) else None
        if ours and obs.distance_m:
            verdicts.append(bool(0.5 <= obs.distance_m / ours <= 2.0))
        else:
            verdicts.append(None)
    evaluated = [v for v in verdicts if v is not None]
    return {
        "classification": "EXTERNAL_LIVE_REFERENCE",
        "requests_metadata": metadata,
        "n_evaluated": len(evaluated),
        "n_within_plausibility_band": sum(evaluated),
        "all_plausible": all(evaluated) if evaluated else None,
        "note": "Derived verdicts only; no Google Maps Content persisted (DECISION 1).",
    }
