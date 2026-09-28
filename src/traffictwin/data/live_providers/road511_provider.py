"""road511 provider — multi-jurisdiction US road-data API (cameras + incidents).

Role in DhakaFlow (fixed, non-negotiable — same lock as ny511_provider):

* Classification is **PROVIDER_INTEGRATION_VALIDATION** plus, at the perception
  gate, **DOMAIN_SHIFT_MEASUREMENT** — US traffic validates no Dhaka claim
  (foreign-data policy, INTEGRATED_BUILD_PLAN §11 use B).
* Key status: **ACTIVE** — verified live 2026-08-25 (200 on /v1/events?WA,
  524 CO cameras). Supersedes the pending 511NY request for the live track.
* Rate limit observed from response headers: **30 requests/minute** on
  api.road511.com. `Road511Provider` enforces a courtesy budget below that;
  the recorder (`scripts/record_road511.py`) schedules well under it.
* Camera snapshot/stream URLs point at state-DOT hosts (e.g. cotrip.org),
  which are NOT behind the road511 rate limit; still fetched politely.

What road511 gives the project that 511NY did not:
incident records with natural-language descriptions and machine fields
(`type`, `sub_type`, `cause`, `severity`, GeoJSON location, `affected_roads`)
— i.e. real congestion labels (`cause: "congestion"`) and free labelled text
for the NLP incident-extraction gate.

Data policy: state-DOT public data re-served by road511; per-jurisdiction
attribution blocks arrive in the payload and are persisted verbatim in raw
captures (Colorado's CDOT terms require a downstream disclaimer — kept with
the data, surfaced by the recorder manifest).

Pattern provenance: structure follows dhakaflow/live/ny511_provider.py (the
proven in-repo provider pattern) per the official-implementation policy —
no structure invented where a validated pattern exists.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable
from traffictwin.configuration import load_credential

from traffictwin.common.reality import Provenance, RealityClass
from traffictwin.data.live_providers.providers import CameraFeedStatus, ObservationStore

ROAD511_BASE = "https://api.road511.com/api/v1"

ROAD511_KEY_STATUS = "ACTIVE"          # verified live 2026-08-25 (events + cameras)

CLASSIFICATION = "PROVIDER_INTEGRATION_VALIDATION"
SECONDARY_CLASSIFICATION = "DOMAIN_SHIFT_MEASUREMENT"
FORBIDDEN_CLASSIFICATION = "DHAKA_LIVE_CAMERA_VALIDATION"

# Provider-side hard limit is 30/min (x-ratelimit-limit header, 2026-08-25).
# We budget under it so bursts from tests + recorder never collide with it.
COURTESY_BUDGET_PER_MIN = 20


def load_road511_key() -> str:
    """Use the same environment/root .env lookup as the web API."""
    return load_credential("ROAD511_API_KEY")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_transport(url: str, api_key: str) -> dict:
    import json
    import urllib.request
    # api.road511.com sits behind Cloudflare, which 403s the default
    # "Python-urllib" user agent (verified 2026-08-25: same key, same URL —
    # curl UA 200, Python-urllib UA 403). Send an honest tool UA instead.
    req = urllib.request.Request(url, headers={
        "X-API-Key": api_key,
        "User-Agent": "dhakaflow-research/0.1 (+thesis; contact via key owner)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _RateGate:
    """Courtesy limiter: at most `per_min` calls per rolling 60 s window."""

    def __init__(self, per_min: int = COURTESY_BUDGET_PER_MIN):
        self._per_min = per_min
        self._stamps: list[float] = []

    def wait(self) -> None:
        now = time.monotonic()
        self._stamps = [t for t in self._stamps if now - t < 60.0]
        if len(self._stamps) >= self._per_min:
            sleep_s = 60.0 - (now - self._stamps[0]) + 0.05
            if sleep_s > 0:
                time.sleep(sleep_s)
        self._stamps.append(time.monotonic())


class Road511Provider:
    """Cameras (`CameraProvider` contract) + incidents over api.road511.com.

    Field names below are normalised defensively against the live payload
    captured 2026-08-25 (WA events, CO cameras); raw payloads are persisted so
    normalisation bugs are recoverable without a re-fetch.
    """

    def __init__(self, store: ObservationStore | None = None,
                 api_key: str | None = None,
                 transport: Callable[[str, str], dict] | None = None,
                 rate_gate: _RateGate | None = None):
        self._key = api_key if api_key is not None else load_road511_key()
        self._transport = transport or _default_transport
        self._store = store
        self._gate = rate_gate or _RateGate()

    @property
    def name(self) -> str:
        return "road511"

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _get(self, path_and_query: str) -> dict:
        if not self.enabled:
            raise RuntimeError(
                "Road511Provider disabled: no ROAD511_API_KEY in env or "
                "the root .env. No data is fabricated meanwhile.")
        self._gate.wait()
        return self._transport(f"{ROAD511_BASE}/{path_and_query}", self._key)

    # ------------------------------------------------------------- cameras --
    def list_cameras(self, bbox: tuple[float, float, float, float],
                     jurisdiction: str = "CO",
                     limit: int = 100) -> list[CameraFeedStatus]:
        """Cameras inside (lat_min, lat_max, lng_min, lng_max) for one state."""
        lat_min, lat_max, lng_min, lng_max = bbox
        clat = (lat_min + lat_max) / 2.0
        clng = (lng_min + lng_max) / 2.0
        payload = self._get(
            f"features?type=cameras&jurisdiction={jurisdiction}"
            f"&lat={clat}&lng={clng}&radius_km=100&limit={limit}")
        captured = _now_utc()
        if self._store:
            # State-DOT public data — raw persistence permitted; the payload's
            # attribution block (licence + required disclaimer) rides along.
            self._store.append_raw(self.name, {"cameras": payload}, captured)

        out: list[CameraFeedStatus] = []
        for cam in payload.get("data", []):
            lat = _to_float(cam.get("latitude"))
            lng = _to_float(cam.get("longitude"))
            if lat is None or lng is None:
                continue
            if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
                continue
            props = cam.get("properties") or {}
            video_url = (props.get("video_url") or "").strip()
            image_url = (props.get("image_url") or "").strip()
            active = bool(cam.get("is_active", False))
            status = CameraFeedStatus(
                camera_id=str(cam.get("id", "")),
                provider=self.name,
                lat=lat, lng=lng,
                # A camera is usable if it is active AND offers either a live
                # HLS stream or at least a refreshing snapshot. Several CO
                # cameras ship video_url: null — snapshot-only is still usable.
                has_stream=active and bool(video_url or image_url),
                freshness_s=None,
                rights={"cv_processing": True,   # public DOT data
                        "retention": True,
                        "public_demo": True},
                provenance=Provenance(
                    provider=self.name,
                    reality=RealityClass.REAL_LIVE,
                    captured_utc=captured,
                    metadata={
                        "endpoint": f"{ROAD511_BASE}/features",
                        "classification": CLASSIFICATION,
                        "secondary": SECONDARY_CLASSIFICATION,
                        "never": FORBIDDEN_CLASSIFICATION,
                        "jurisdiction": str(cam.get("jurisdiction", "")),
                        "road": str(cam.get("road_name", "")),
                        "name": str(cam.get("name", "")),
                        "video_url": video_url,
                        "image_url": image_url,
                    }),
            )
            if self._store:
                self._store.append_normalized(status)
            out.append(status)
        return out

    # ------------------------------------------------------------ incidents --
    def list_events(self, jurisdiction: str, limit: int = 100,
                    offset: int = 0) -> list[dict]:
        """Active events for one jurisdiction, normalised to flat records.

        Returns plain dicts (persisted via the store) rather than a new
        platform type: the NLP gate consumes `description` verbatim, and the
        congestion-labeller consumes the machine fields — neither needs a
        frozen dataclass yet. A platform type is introduced when a gate
        KEEP-decides this feed, not before.
        """
        payload = self._get(
            f"events?jurisdiction={jurisdiction}&limit={limit}&offset={offset}")
        captured = _now_utc()
        if self._store:
            self._store.append_raw(
                self.name, {"events": payload, "jurisdiction": jurisdiction},
                captured)

        out: list[dict] = []
        for ev in payload.get("data", []):
            out.append({
                "id": str(ev.get("id", "")),
                "jurisdiction": str(ev.get("jurisdiction", "")),
                "type": str(ev.get("type", "")),
                "sub_type": str(ev.get("sub_type", "") or ""),
                "cause": str(ev.get("cause", "") or ""),
                "severity": str(ev.get("severity", "") or ""),
                "status": str(ev.get("status", "") or ""),
                "title": str(ev.get("title", "") or ""),
                "description": str(ev.get("description", "") or ""),
                "affected_roads": list(ev.get("affected_roads") or []),
                "direction": str(ev.get("direction", "") or ""),
                "latitude": _to_float(ev.get("latitude")),
                "longitude": _to_float(ev.get("longitude")),
                "road_class": str(ev.get("road_class", "") or ""),
                "start_time": str(ev.get("start_time", "") or ""),
                "end_time": str(ev.get("end_time", "") or ""),
                "last_updated": str(ev.get("last_updated", "") or ""),
                "captured_utc": captured,
                "classification": CLASSIFICATION,
            })
        return out
