"""Snapping a trace to the road: the city's own Valhalla server (map matching, `trace_attributes`) when the city declares
one; else Amazon Location Routes `SnapToRoads` when AWS is configured; otherwise no snapping, said so in every record.
Nothing is estimated in the gap."""
from __future__ import annotations

from typing import Protocol

from core.common import credentials

SOURCE = "amazon_location"
MAX_TRACE = 100                      # points per SnapToRoads call


class Snapper(Protocol):
    name: str
    def snap(self, points: list[dict]) -> list[dict]: ...      # each: lat, lng, recorded_at (ISO), heading?, speed_kmh?


class NoSnap:
    name = "none"
    def snap(self, points: list[dict]) -> list[dict]:
        return [{**p, "snapped_lat": None, "snapped_lng": None, "snap_confidence": None} for p in points]


class AmazonSnap:
    name = SOURCE

    @property
    def configured(self) -> bool:
        return bool(credentials.load("AWS_ACCESS_KEY_ID") and credentials.load("AWS_SECRET_ACCESS_KEY"))

    def _client(self):
        import boto3
        region = credentials.load("AWS_LOCATION_REGION") or credentials.load("AWS_REGION") or "us-east-1"
        return boto3.client("geo-routes", region_name=region, aws_access_key_id=credentials.load("AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=credentials.load("AWS_SECRET_ACCESS_KEY"),
                            aws_session_token=credentials.load("AWS_SESSION_TOKEN") or None)

    def snap(self, points: list[dict]) -> list[dict]:
        out = []
        client = self._client()
        for i in range(0, len(points), MAX_TRACE):
            chunk = points[i:i + MAX_TRACE]
            trace = [{"Position": [p["lng"], p["lat"]], "Timestamp": p["recorded_at"],
                      **({"Heading": float(p["heading"])} if p.get("heading") is not None else {}),
                      **({"Speed": float(p["speed_kmh"])} if p.get("speed_kmh") is not None else {})} for p in chunk]
            resp = client.snap_to_roads(TracePoints=trace, TravelMode="Car", SnapRadius=50)
            snapped = resp.get("SnappedTracePoints", [])
            for p, s in zip(chunk, snapped + [{}] * (len(chunk) - len(snapped))):
                pos = s.get("SnappedPosition")
                out.append({**p, "snapped_lat": pos[1] if pos else None, "snapped_lng": pos[0] if pos else None,
                            "snap_confidence": s.get("Confidence")})
        return out


class ValhallaSnap:
    """Map matching on the city's own routing server: each fix moved onto the road the trace most likely followed, with
    the OpenStreetMap way it landed on. Confidence is 1 for a matched point, 0.5 for one interpolated between matches."""
    name = "valhalla"

    def __init__(self, city_id: str):
        self.city_id = city_id

    @property
    def configured(self) -> bool:
        from core.simulation.routing import valhalla
        refused, _, _ = valhalla._server(self.city_id)
        return refused is None

    def snap(self, points: list[dict]) -> list[dict]:
        from core.simulation.routing import valhalla
        out = []
        for i in range(0, len(points), MAX_TRACE):
            chunk = points[i:i + MAX_TRACE]
            got = valhalla.trace(self.city_id, [{"lat": p["lat"], "lng": p["lng"], "time": _epoch(p.get("recorded_at"))} for p in chunk])
            if not got.get("available") and got.get("code") == "no_path":          # the timed trace is implausible to the matcher (a jump): once more on positions alone
                got = valhalla.trace(self.city_id, [{"lat": p["lat"], "lng": p["lng"]} for p in chunk])
            matched = got.get("matched", []) if got.get("available") else []
            for p, m in zip(chunk, matched + [{}] * (len(chunk) - len(matched))):
                out.append({**p, "snapped_lat": m.get("lat"), "snapped_lng": m.get("lng"),
                            "snap_confidence": None if m.get("lat") is None else (1.0 if m.get("type") == "matched" else 0.5), "way_id": m.get("way_id")})
        return out


def _epoch(iso: str | None) -> int | None:
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()) if iso else None
    except ValueError:
        return None


def default(city_id: str | None = None) -> Snapper:
    """The city's own server first, a provider second, nothing third."""
    if city_id:
        v = ValhallaSnap(city_id)
        if v.configured:
            return v
    a = AmazonSnap()
    return a if a.configured else NoSnap()
