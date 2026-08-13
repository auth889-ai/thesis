"""SUMO-free unit tests for the Lab 02 v2 additions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))   # repo root

from src.regions import CANDIDATES  # noqa: E402
from src.osm.download import overpass_query  # noqa: E402
from src.analysis.cross_validate import sumo_junction_osmids  # noqa: E402
from src.live_reference.google_routes import GoogleRoutesReference  # noqa: E402
from dhakaflow.common.live_reference import (LiveRouteRequest,  # noqa: E402
                                             LiveTrafficReference)


def test_five_candidates_frozen_with_valid_bboxes():
    assert set(CANDIDATES) == {"R1", "R2", "R3", "R4", "R5"}
    for spec in CANDIDATES.values():
        b = spec["bbox"]
        assert b["south"] < b["north"] and b["west"] < b["east"]
        assert 23.5 < b["south"] < 24.0 and 90.3 < b["west"] < 90.5  # Dhaka


def test_context_query_adds_selection_features_to_same_snapshot():
    bbox = CANDIDATES["R1"]["bbox"]
    plain = overpass_query(bbox)
    ctx = overpass_query(bbox, include_context=True)
    assert 'way["highway"]' in plain and "bus_stop" not in plain
    for needle in ("bus_stop", 'relation["route"="bus"]', "hospital",
                   "surveillance", "crossing"):
        assert needle in ctx
    assert 'way["highway"]' in ctx          # network part unchanged


def test_cluster_id_expansion_to_osm_node_sets():
    assert sumo_junction_osmids("123456") == {123456}
    assert sumo_junction_osmids("cluster_11_22_33") == {11, 22, 33}
    assert sumo_junction_osmids("joinedS_cluster_7_8_#2more") == {7, 8, 2}


def test_live_reference_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    ref = GoogleRoutesReference()
    assert isinstance(ref, LiveTrafficReference)     # structural conformance
    assert not ref.enabled
    obs = ref.travel_time(LiveRouteRequest(23.75, 90.39, 23.73, 90.38))
    assert obs.status == "DISABLED_NO_KEY"
    assert obs.duration_s is None and obs.distance_m is None   # missing != 0
    assert obs.classification == "EXTERNAL_LIVE_REFERENCE"


def test_live_reference_mock_transport_and_persistable_metadata():
    def mock_transport(body, headers):
        assert headers["X-Goog-FieldMask"].count("polyline") == 0   # DECISION 1
        assert body["routingPreference"] == "TRAFFIC_AWARE"
        return {"routes": [{"duration": "600s", "staticDuration": "420s",
                            "distanceMeters": 5000}]}

    ref = GoogleRoutesReference(transport=mock_transport)
    assert ref.enabled
    obs = ref.travel_time(LiveRouteRequest(23.75, 90.39, 23.73, 90.38, label="T1"))
    assert obs.ok and obs.duration_s == 600.0 and obs.static_duration_s == 420.0
    meta = obs.persistable_metadata()
    # ONLY metadata may be persisted — never durations/distances (DECISION 1)
    assert "duration_s" not in meta and "distance_m" not in meta
    assert meta["status"] == "OK" and meta["label"] == "T1"


def test_live_route_request_rejects_unknown_preference():
    import pytest
    with pytest.raises(ValueError):
        LiveRouteRequest(23.7, 90.4, 23.8, 90.4, routing_preference="FASTEST")
