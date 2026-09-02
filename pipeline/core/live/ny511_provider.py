"""511NY camera provider — free NYSDOT developer API, key-gated.

Role in DhakaFlow (fixed, non-negotiable):

* Classification is **PROVIDER_INTEGRATION_VALIDATION** — proof that the
  provider-neutral `CameraProvider` runtime ingests a true external live feed.
  It is **never** `DHAKA_LIVE_CAMERA_VALIDATION`; New York traffic validates no
  Dhaka claim (foreign-data policy, INTEGRATED_BUILD_PLAN §11 use B).
* Key status: **PENDING_EXTERNAL_APPROVAL** — the developer-key request was
  submitted 2026-08-19 and 511NY approval is a human process on their side.
  The status constant below is flipped by `scripts/verify_511ny.py` evidence,
  never by hand.

Key handling: canonical env var is ``NY511_API_KEY`` (POSIX env names cannot
begin with a digit, so the literal "511NY_API_KEY" is not usable as an env
var). The `dhakaflow/.env` file is also honoured, accepting either
``NY511_API_KEY=...`` or ``API_KEY_511NY=...``. Without a key the provider is
`enabled=False` and refuses to fetch — no data is ever fabricated.

Data policy: 511NY is public government data (free developer program). Raw
payloads MAY be persisted, unlike Google Routes content. Still captured through
the same split raw/normalized `ObservationStore`.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..common.reality import Provenance, RealityClass
from .providers import CameraFeedStatus, ObservationStore

NY511_ENDPOINT = "https://511ny.org/api/getcameras"

# Flipped only by verify_511ny.py evidence on first successful live call.
NY511_KEY_STATUS = "PENDING_EXTERNAL_APPROVAL"

CLASSIFICATION = "PROVIDER_INTEGRATION_VALIDATION"
FORBIDDEN_CLASSIFICATION = "DHAKA_LIVE_CAMERA_VALIDATION"


def load_ny511_key() -> str:
    """Env var first, then dhakaflow/.env (either accepted spelling)."""
    key = os.environ.get("NY511_API_KEY", "")
    if key:
        return key
    envf = Path(__file__).resolve().parents[1] / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            m = re.match(
                r'\s*(?:export\s+)?(?:NY511_API_KEY|API_KEY_511NY)\s*=\s*'
                r'["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    return ""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_transport(url: str) -> list | dict:
    import json
    import urllib.request
    with urllib.request.urlopen(
            urllib.request.Request(url), timeout=20) as resp:
        return json.loads(resp.read())


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class NY511CameraProvider:
    """`CameraProvider` over the 511NY getcameras endpoint.

    The response schema is normalised defensively (field names verified against
    the 511NY developer docs, to be re-captured verbatim on the first live call
    by `scripts/verify_511ny.py`).
    """

    def __init__(self, store: ObservationStore | None = None,
                 api_key: str | None = None,
                 transport: Callable[[str], list | dict] | None = None):
        self._key = api_key if api_key is not None else load_ny511_key()
        self._transport = transport or _default_transport
        self._store = store

    @property
    def name(self) -> str:
        return "ny511_cameras"

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def list_cameras(self, bbox: tuple[float, float, float, float]
                     ) -> list[CameraFeedStatus]:
        """Cameras inside (lat_min, lat_max, lng_min, lng_max)."""
        if not self.enabled:
            raise RuntimeError(
                "NY511CameraProvider disabled: no NY511_API_KEY. Key status is "
                f"{NY511_KEY_STATUS} — request submitted, approval pending on "
                "the 511NY side. When approved: export NY511_API_KEY=... and "
                "run scripts/verify_511ny.py. No data is fabricated meanwhile.")

        url = f"{NY511_ENDPOINT}?key={self._key}&format=json"
        payload = self._transport(url)
        captured = _now_utc()
        if self._store:
            # Public government data — raw persistence permitted.
            self._store.append_raw(self.name, {"cameras": payload}, captured)

        lat_min, lat_max, lng_min, lng_max = bbox
        out: list[CameraFeedStatus] = []
        for cam in (payload if isinstance(payload, list) else []):
            lat = _to_float(cam.get("Latitude"))
            lng = _to_float(cam.get("Longitude"))
            if lat is None or lng is None:
                continue
            if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
                continue
            video_url = (cam.get("VideoUrl") or "").strip()
            disabled = bool(cam.get("Disabled", False))
            blocked = bool(cam.get("Blocked", False))
            status = CameraFeedStatus(
                camera_id=str(cam.get("ID", "")),
                provider=self.name,
                lat=lat, lng=lng,
                has_stream=bool(video_url) and not disabled and not blocked,
                freshness_s=None,   # 511NY does not publish per-frame age
                rights={"cv_processing": True,   # public data, free dev program
                        "retention": True,
                        "public_demo": True},
                provenance=Provenance(
                    provider=self.name,
                    reality=RealityClass.REAL_LIVE,
                    captured_utc=captured,
                    metadata={
                        "endpoint": NY511_ENDPOINT,
                        "classification": CLASSIFICATION,
                        "never": FORBIDDEN_CLASSIFICATION,
                        "roadway": str(cam.get("RoadwayName", "")),
                        "name": str(cam.get("Name", "")),
                    }),
            )
            if self._store:
                self._store.append_normalized(status)
            out.append(status)
        return out
