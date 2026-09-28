"""Genuine detector metadata -> SUMO edges: published ids and coordinates only, snapped and graded,
rejected outside the scenario, and consumed by the route optimizer as the corridor map."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.city import sensor_map as sm  # noqa: E402

MAPPING = REPO / "data/cities/los_angeles_metr/sumo/sensor_to_edge.json"
needs_la = pytest.mark.skipif(not (MAPPING.exists() and sm.LOCATIONS.exists()), reason="LA scenario or pinned DCRNN metadata not present here")


def test_match_requires_index_and_coordinate_agreement():
    rows = [{"sensor_id": "1", "latitude": "34.1", "longitude": "-118.2"}, {"sensor_id": "2", "latitude": "34.2", "longitude": "-118.3"}]
    meta = {"nodes": ["a", "b", "c"], "coords": [[34.1, -118.2], [34.25, -118.3], [34.3, -118.4]]}
    m = sm.match_nodes(meta, rows)
    assert m[0]["sensor_id"] == "1" and m[0]["coordinate_match"]
    assert m[1]["sensor_id"] is None and not m[1]["coordinate_match"]      # same index, different coordinate: not accepted
    assert m[2]["sensor_id"] is None                                          # beyond the published file


@needs_la
def test_la_mapping_is_genuine_graded_and_bounded():
    d = json.loads(MAPPING.read_text())
    assert d["dataset"] == "user:los_angeles" and d["source"]["commit"] and d["source"]["file_sha256"]
    rows = {r["sensor_id"]: r for r in sm.genuine_rows()}
    good = [r for r in d["records"] if r["quality"] == "GOOD"]
    assert len(good) >= 6
    s, w, n, e = d["bbox"]
    for r in good:
        assert r["sensor_id"] in rows and abs(float(rows[r["sensor_id"]]["latitude"]) - r["lat"]) < 1e-5
        assert r["snap_m"] <= sm.GOOD_M and r["edge_type"] in sm.MAJOR and s <= r["lat"] <= n and w <= r["lon"] <= e
    for r in d["records"]:
        if r["quality"] == "REJECTED":
            assert r["edge"] is None and r["reason"]
    assert d["counts"]["GOOD"] == len(good)


@needs_la
def test_mapping_becomes_the_optimizer_corridor_map():
    d = sm.find_for_dataset("user:los_angeles")
    assert d and d["city_id"] == "los_angeles_metr" and d["file_hash"]
    cmap, free, facts = sm.corridor_map(d)
    assert cmap and all(len(v["edges"]) == 1 for v in cmap.values())
    assert all(free[k] > 0 for k in cmap) and all(facts[k]["sensor_id"] for k in cmap)
    assert sm.find_for_dataset("user:no_such_dataset") is None


def test_speed_units_reach_the_cost_builder_in_metres_per_second():
    sys.path.insert(0, str(REPO / "src/dashboard/backend"))
    import route_opt
    v, u = route_opt.to_mps({"a": 72.0, "b": None}, "speed km/h")
    assert u == "speed_mps" and v["a"] == pytest.approx(20.0) and v["b"] is None
    v, u = route_opt.to_mps({"a": 2.5}, "congestion_level_0_3")
    assert u == "congestion_level_0_3" and v["a"] == 2.5
    v, u = route_opt.to_mps({"a": 60.0}, "speed mph")
    assert v["a"] == pytest.approx(26.82, abs=0.01)


def test_dataset_run_without_mapping_is_refused_not_guessed():
    sys.path.insert(0, str(REPO / "src/dashboard/backend"))
    import route_opt
    with pytest.raises(route_opt.NoStoredForecast, match="NO_SENSOR_MAPPING"):
        route_opt.corridor_map_for({"run_id": "an_x", "city": "user:no_such_dataset"})
