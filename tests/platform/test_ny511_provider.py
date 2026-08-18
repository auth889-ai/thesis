"""511NY provider tests — fixture transport only.

Real-provider validation stays PENDING_EXTERNAL_APPROVAL until the developer
key is approved; these tests prove the integration code, never the live feed.
"""
from __future__ import annotations

import json

import pytest

from dhakaflow.common.reality import RealityClass
from dhakaflow.live.ny511_provider import (CLASSIFICATION,
                                           FORBIDDEN_CLASSIFICATION,
                                           NY511_KEY_STATUS,
                                           NY511CameraProvider)
from dhakaflow.live.providers import CameraProvider, ObservationStore

# Shape from the 511NY developer docs; re-captured verbatim at activation.
FIXTURE = [
    {"ID": "NY-101", "Name": "I-95 @ Alexander Hamilton Bridge",
     "RoadwayName": "I-95", "DirectionOfTravel": "Northbound",
     "Latitude": 40.7484, "Longitude": -73.9857,
     "Url": "https://s3.example/frame101.jpg",
     "VideoUrl": "https://stream.example/101.m3u8",
     "Disabled": False, "Blocked": False},
    {"ID": "NY-102", "Name": "Disabled camera",
     "Latitude": 40.75, "Longitude": -73.98,
     "VideoUrl": "https://stream.example/102.m3u8",
     "Disabled": True, "Blocked": False},
    {"ID": "NY-103", "Name": "Stillframe only, no stream",
     "Latitude": 40.76, "Longitude": -73.97,
     "Url": "https://s3.example/frame103.jpg", "VideoUrl": "",
     "Disabled": False, "Blocked": False},
    {"ID": "NY-999", "Name": "Buffalo — outside test bbox",
     "Latitude": 42.8864, "Longitude": -78.8784,
     "VideoUrl": "https://stream.example/999.m3u8",
     "Disabled": False, "Blocked": False},
    {"ID": "NY-BAD", "Name": "No coordinates", "Latitude": None,
     "Longitude": None, "VideoUrl": "x"},
]

NYC_BBOX = (40.70, 40.80, -74.02, -73.93)


def _provider(store=None, key="test-key"):
    return NY511CameraProvider(store=store, api_key=key,
                               transport=lambda url: json.loads(json.dumps(FIXTURE)))


def test_key_status_is_pending_external_approval():
    assert NY511_KEY_STATUS == "PENDING_EXTERNAL_APPROVAL"


def test_satisfies_camera_provider_protocol():
    assert isinstance(_provider(), CameraProvider)


def test_disabled_without_key_and_never_fabricates():
    p = NY511CameraProvider(api_key="", transport=lambda url: FIXTURE)
    assert not p.enabled
    with pytest.raises(RuntimeError, match="PENDING_EXTERNAL_APPROVAL"):
        p.list_cameras(NYC_BBOX)


def test_bbox_filter_and_stream_flags():
    cams = _provider().list_cameras(NYC_BBOX)
    ids = {c.camera_id: c for c in cams}
    assert set(ids) == {"NY-101", "NY-102", "NY-103"}   # Buffalo + bad excluded
    assert ids["NY-101"].has_stream                     # live video
    assert not ids["NY-102"].has_stream                 # disabled
    assert not ids["NY-103"].has_stream                 # stillframe only


def test_classification_is_integration_never_dhaka():
    cam = _provider().list_cameras(NYC_BBOX)[0]
    md = cam.provenance.metadata
    assert md["classification"] == CLASSIFICATION == "PROVIDER_INTEGRATION_VALIDATION"
    assert md["never"] == FORBIDDEN_CLASSIFICATION == "DHAKA_LIVE_CAMERA_VALIDATION"
    assert cam.provenance.reality is RealityClass.REAL_LIVE


def test_raw_and_normalized_persisted_separately(tmp_path):
    store = ObservationStore(tmp_path)
    cams = _provider(store=store).list_cameras(NYC_BBOX)
    raw = (tmp_path / "raw" / "ny511_cameras.jsonl").read_text().splitlines()
    norm = (tmp_path / "normalized" / "ny511_cameras.jsonl").read_text().splitlines()
    assert len(raw) == 1                       # one fetch, full payload
    assert len(json.loads(raw[0])["payload"]["cameras"]) == len(FIXTURE)
    assert len(norm) == len(cams)              # one line per in-bbox camera
