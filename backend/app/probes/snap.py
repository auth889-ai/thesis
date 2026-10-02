"""Snapping a trace to the road: Amazon Location Routes `SnapToRoads` when AWS is configured, otherwise
no snapping, said so in every record. Nothing is estimated in the gap."""
from __future__ import annotations

from typing import Protocol

from app import credentials

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


def default() -> Snapper:
    a = AmazonSnap()
    return a if a.configured else NoSnap()
