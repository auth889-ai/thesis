"""road511 provider tests — fixture transport only.

The live feed was verified 2026-08-25 (WA events 200, 524 CO cameras); these
tests prove the integration code deterministically, mirroring
test_ny511_provider.py per the in-repo pattern rule. Fixture shapes are taken
from the REAL captured payloads (results/artifacts/road511_recordings/raw/), not
invented.
"""
from __future__ import annotations

import json

import pytest

from pipeline.core.common.reality import RealityClass
from pipeline.core.live.providers import CameraProvider, ObservationStore
from pipeline.core.live.road511_provider import (CLASSIFICATION,
                                             FORBIDDEN_CLASSIFICATION,
                                             ROAD511_KEY_STATUS,
                                             Road511Provider)

# Shape captured live 2026-08-25 from /v1/features?type=cameras (CO).
CAMERAS_FIXTURE = {
    "attribution": [{"source_code": "CO",
                     "source_name": "Colorado — COtrip (CDOT)",
                     "license": "CDOT Terms of Service Policy"}],
    "data": [
        {"id": "CO-cam-9179", "jurisdiction": "CO", "feature_type": "cameras",
         "name": "US 85 MP 230.30 SB at E 124th Ave in Brighton",
         "latitude": 39.9217, "longitude": -104.85314, "road_name": "US 85",
         "is_active": True,
         "properties": {"image_url": "https://cocam.example/085S.png",
                        "video_url": "https://stream.example/085S/playlist.m3u8"}},
        # Real observed case: active camera with video_url null (snapshot only)
        {"id": "CO-cam-8663", "jurisdiction": "CO", "feature_type": "cameras",
         "name": "US 6 MP 274.65 EB at Johnson Rd in Golden",
         "latitude": 39.72491, "longitude": -105.19837, "road_name": "US 6",
         "is_active": True,
         "properties": {"image_url": "https://cocam.example/006E.png"}},
        # Inactive camera — must be excluded from usable
        {"id": "CO-cam-DEAD", "jurisdiction": "CO", "feature_type": "cameras",
         "name": "dead", "latitude": 39.7, "longitude": -104.9,
         "is_active": False,
         "properties": {"video_url": "https://stream.example/dead.m3u8"}},
        # Outside the test bbox
        {"id": "CO-cam-FAR", "jurisdiction": "CO", "feature_type": "cameras",
         "name": "far", "latitude": 37.0, "longitude": -104.9,
         "is_active": True, "properties": {"image_url": "x"}},
        # Missing coordinates — must be skipped, never crash
        {"id": "CO-cam-BAD", "jurisdiction": "CO", "feature_type": "cameras",
         "name": "bad", "latitude": None, "longitude": None,
         "is_active": True, "properties": {}},
    ],
    "total": 5, "limit": 100, "offset": 0, "has_more": False,
}

# Shape captured live 2026-08-25 from /v1/events (WA).
EVENTS_FIXTURE = {
    "data": [
        {"id": "WA-711122", "jurisdiction": "WA", "type": "closure",
         "sub_type": "lane_closure", "cause": "congestion",
         "severity": "major", "status": "active",
         "title": "Lane Closure — US 90",
         "description": "Right Lane Closure for roadwork on I-90 eastbound...",
         "affected_roads": ["US 90"], "direction": "eastbound",
         "latitude": 47.681675981, "longitude": -117.085712776,
         "road_class": "us_highway",
         "start_time": "2026-08-25T05:14:00Z",
         "end_time": "2026-08-25T10:00:00Z",
         "last_updated": "2026-08-25T06:27:08.802393Z"},
        {"id": "WA-711112", "jurisdiction": "WA", "type": "incident",
         "sub_type": "accident", "cause": "accident", "severity": "major",
         "status": "active", "title": "Collision — US 5",
         "description": "On I-5 northbound at Alger there is a collision...",
         "affected_roads": ["US 5"], "direction": "northbound",
         "latitude": 48.622183374, "longitude": -122.356374518,
         "road_class": "us_highway",
         "start_time": "2026-08-25T04:49:00Z",
         "last_updated": "2026-08-25T04:52:30.142227Z"},
    ],
    "total": 2, "limit": 5, "offset": 0, "has_more": False,
}

DENVER_BBOX = (39.4, 40.1, -105.5, -104.6)


def _provider(store=None, key="test-key", fixture=None):
    payload = fixture if fixture is not None else CAMERAS_FIXTURE
    return Road511Provider(
        store=store, api_key=key,
        transport=lambda url, k: json.loads(json.dumps(payload)))


def test_key_status_is_active():
    assert ROAD511_KEY_STATUS == "ACTIVE"


def test_satisfies_camera_provider_protocol():
    assert isinstance(_provider(), CameraProvider)


def test_disabled_without_key_and_never_fabricates():
    p = Road511Provider(api_key="",
                        transport=lambda url, k: CAMERAS_FIXTURE)
    assert not p.enabled
    with pytest.raises(RuntimeError, match="No data is fabricated"):
        p.list_cameras(DENVER_BBOX)
    with pytest.raises(RuntimeError, match="No data is fabricated"):
        p.list_events("WA")


def test_cameras_bbox_active_and_null_video_handling():
    cams = _provider().list_cameras(DENVER_BBOX)
    ids = {c.camera_id for c in cams}
    assert ids == {"CO-cam-9179", "CO-cam-8663", "CO-cam-DEAD"}
    by_id = {c.camera_id: c for c in cams}
    assert by_id["CO-cam-9179"].has_stream            # HLS + snapshot
    assert by_id["CO-cam-8663"].has_stream            # snapshot-only is usable
    assert not by_id["CO-cam-DEAD"].has_stream        # inactive excluded


def test_classification_lock_on_every_camera():
    for c in _provider().list_cameras(DENVER_BBOX):
        assert c.provenance.reality is RealityClass.REAL_LIVE
        assert c.provenance.metadata["classification"] == CLASSIFICATION
        assert c.provenance.metadata["never"] == FORBIDDEN_CLASSIFICATION


def test_events_normalised_with_congestion_label():
    evs = _provider(fixture=EVENTS_FIXTURE).list_events("WA", limit=5)
    assert len(evs) == 2
    congestion = [e for e in evs if e["cause"] == "congestion"]
    assert len(congestion) == 1
    ev = congestion[0]
    assert ev["id"] == "WA-711122"
    assert ev["severity"] == "major"
    assert ev["description"]                          # NLP-gate raw text kept
    assert ev["classification"] == CLASSIFICATION
    assert ev["latitude"] == pytest.approx(47.6817, abs=1e-3)


def test_store_receives_raw_and_normalized(tmp_path):
    store = ObservationStore(tmp_path)
    p = _provider(store=store)
    p.list_cameras(DENVER_BBOX)
    raw = (tmp_path / "raw" / "road511.jsonl").read_text().splitlines()
    norm = (tmp_path / "normalized" / "road511.jsonl").read_text().splitlines()
    assert len(raw) == 1                               # one raw capture
    assert len(norm) == 3                              # one line per bbox camera
    # Raw capture keeps the provider's attribution block verbatim.
    assert "COtrip" in raw[0]
