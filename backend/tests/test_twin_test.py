"""TEST IN DIGITAL TWIN is causally tied to the AnalysisRun: its O/D become SUMO edges, an unknown
run is refused, an unmappable trip fails loudly, and the seed is generated and recorded."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
REPO = Path(__file__).resolve().parents[2]
NET = REPO / "data/cities/rangpur_city/sumo/rangpur_city.net.xml"
needs_net = pytest.mark.skipif(not NET.exists(), reason="Rangpur scenario not built on this machine")


def _rec(run_id, o, d, city="Rangpur"):
    return {"run_id": run_id, "status": "done", "city": city, "origin_resolved": o, "destination_resolved": d, "requested_model": "auto",
            "resolved_model": "none", "horizon_min": 30, "raw_prediction_hash": "x", "postprocessed_prediction_hash": "y", "route_geometry_hash": "g"}


def test_unknown_analysis_run_is_404(client):
    r = client.post("/api/twin/test", json={"analysis_run_id": "an_does_not_exist"})
    assert r.status_code == 404 and "ANALYSIS_RUN_NOT_FOUND" in r.json()["error"]
    r2 = client.post("/api/twin/test", json={})
    assert r2.json()["started"] is False and "ANALYSIS_RUN_NOT_FOUND" in r2.json()["error"]


def test_seed_is_generated_from_the_run_and_never_a_fixed_research_seed():
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    a, b = twin_test.runtime_seed("an_aaaaaaaa"), twin_test.runtime_seed("an_bbbbbbbb")
    assert a != b and 100 <= a < 1000 and twin_test.runtime_seed("an_aaaaaaaa") == a
    assert a not in (11, 12, 13) and b not in (11, 12, 13)


@needs_net
def test_od_maps_to_edges_and_a_different_destination_gives_a_different_edge():
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    medical = {"lat": 25.7666498, "lng": 89.2338772, "label": "Rangpur Medical College"}
    station = {"lat": 25.7284973, "lng": 89.2634621, "label": "Rangpur Railway Station"}
    university = {"lat": 25.7501, "lng": 89.2717, "label": "Begum Rokeya University"}
    m1 = twin_test.map_od(str(NET), medical, station)
    m2 = twin_test.map_od(str(NET), medical, university)
    assert m1["origin"]["edge"] == m2["origin"]["edge"]
    assert m1["destination"]["edge"] != m2["destination"]["edge"]
    assert m1["origin"]["distance_m"] <= twin_test.NEAR_M and m1["destination"]["distance_m"] <= twin_test.NEAR_M


@needs_net
def test_unmappable_trip_fails_loudly_not_silently():
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    far = {"lat": 25.90, "lng": 89.60, "label": "outside the network"}
    with pytest.raises(twin_test.ODMappingFailed, match="SUMO_OD_MAPPING_FAILED"):
        twin_test.map_od(str(NET), far, far)


def test_scenario_choice_follows_the_analysis_run(monkeypatch):
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    dhaka = _rec("an_d", {"lat": 23.7561, "lng": 90.3872, "label": "Farmgate"}, {"lat": 23.7386, "lng": 90.3954, "label": "Shahbagh"}, city="Dhaka")
    assert twin_test.is_dhaka_run(dhaka)
    rangpur = _rec("an_r", {"lat": 25.7666, "lng": 89.2339, "label": "RMC"}, {"lat": 25.7285, "lng": 89.2635, "label": "station"})
    assert not twin_test.is_dhaka_run(rangpur)


def test_provenance_record_links_back_to_the_analysis(tmp_path, monkeypatch):
    from traffictwin.data import provenance
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    monkeypatch.setattr(provenance, "DIR", tmp_path)
    provenance.save({"run_id": "an_link", "status": "done", "origin_resolved": {"lat": 1, "lng": 2}, "destination_resolved": {"lat": 1, "lng": 2}})
    twin_test._link_analysis("an_link", "sim_x")
    assert provenance.load("an_link")["simulation_run_ids"] == ["sim_x"]
