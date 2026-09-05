"""Forecast -> continuous edge costs -> SUMO candidates -> capacity-aware admission, on a small
official netgenerate grid so the tests need only the pinned SUMO binaries."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.routing import edge_costs as ec, route_optimizer as ro  # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("netgenerate") is None or shutil.which("duarouter") is None, reason="SUMO binaries not installed")


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    d = tmp_path_factory.mktemp("grid")
    net = d / "grid.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", "6", "--grid.length", "200", "--default.speed", "13.89", "--default.lanenumber", "1",
                    "--output-file", str(net), "--no-warnings"], check=True, capture_output=True)
    return net


def _corridor_map(net):
    import sumolib
    n = sumolib.net.readNet(str(net))
    e = n.getEdge("A0B0") if "A0B0" in {x.getID() for x in n.getEdges()} else n.getEdges()[0]
    return {"c1": {"edges": [e.getID()]}}, e.getID()


@needs_sumo
def test_costs_are_continuous_in_the_forecast_and_bounded(grid):
    cmap, eid = _corridor_map(grid)
    tt = {}
    for lvl in (1.9, 2.0, 2.1):
        t = ec.build({"c1": lvl}, "congestion_level_0_3", cmap, grid, 15, hops=0, model="t")
        tt[lvl] = t["edges"][eid]["future_tt_s"]
    assert tt[1.9] < tt[2.0] < tt[2.1], "a fractional level must price differently from its neighbours (no class step)"
    row = ec.build({"c1": 3.0}, "congestion_level_0_3", cmap, grid, 15, hops=0)["edges"][eid]
    assert row["bounded_speed_mps"] <= row["speed_limit_mps"] and row["bounded_speed_mps"] >= 1.0
    assert abs(row["future_tt_s"] - row["length_m"] / row["bounded_speed_mps"]) < 1e-2
    assert row["source"] == "DIRECT" and row["graph_distance"] == 0 and row["decay_weight"] == 1.0
    free = ec.build({"c1": 0.0}, "congestion_level_0_3", cmap, grid, 15, hops=0)["edges"][eid]
    assert free["future_tt_s"] >= free["free_flow_tt_s"]


@needs_sumo
def test_derived_coverage_is_labelled_and_decayed(grid):
    cmap, eid = _corridor_map(grid)
    t0 = ec.build({"c1": 2.5}, "congestion_level_0_3", cmap, grid, 15, hops=0)
    t1 = ec.build({"c1": 2.5}, "congestion_level_0_3", cmap, grid, 15, hops=1)
    t2 = ec.build({"c1": 2.5}, "congestion_level_0_3", cmap, grid, 15, hops=2)
    assert t0["priced_edges"] == 1 < t1["priced_edges"] < t2["priced_edges"]
    d1 = [r for r in t1["edges"].values() if r["source"] == "DERIVED"]
    assert d1 and all(r["graph_distance"] == 1 and r["decay_weight"] == 0.6 for r in d1)
    direct_ratio = t1["edges"][eid]["ratio"]
    assert all(1.0 < r["ratio"] < direct_ratio for r in d1)
    assert any(r["graph_distance"] == 2 and r["decay_weight"] == 0.35 for r in t2["edges"].values())
    assert t0["future_cost_hash"] != t1["future_cost_hash"] != t2["future_cost_hash"]
    assert t1["config"]["_config_hash"] and t1["config"]["_config_file"].endswith("routing_config.json")


@needs_sumo
def test_candidates_come_from_duarouter_and_the_real_count_is_reported(grid, tmp_path):
    cmap, eid = _corridor_map(grid)
    table = ec.build({"c1": 3.0}, "congestion_level_0_3", cmap, grid, 15, hops=1)
    trips = [{"id": "v1", "from": "A0A1", "to": "E4E5", "depart": 0.0}]
    rec = ro.optimize(grid, trips, table, tmp_path / "o", seed=7, window_s=1800)
    d = rec["decisions"][0]
    assert 1 <= d["candidates_real"] <= d["candidates_requested"] + 1
    assert rec["generator"]["runs"][1]["random_factor"] is None and rec["generator"]["runs"][2]["random_factor"] == 1.5
    c = d["candidates"][0]
    for k in ("route_id", "edges", "base_tt_s", "forecast_future_tt_s", "distance_m", "overlap_with_current", "predicted_load_ratio_max",
              "load_penalty_s", "overlap_penalty_s", "final_cost_s"):
        assert k in c
    assert abs(c["final_cost_s"] - (c["forecast_future_tt_s"] + c["load_penalty_s"] + c["overlap_penalty_s"])) < 1e-3
    assert c["is_current"] and c["overlap_penalty_s"] == 0.0


@needs_sumo
def test_threshold_blocks_tiny_gains_and_records_the_terms(grid, tmp_path):
    cmap, eid = _corridor_map(grid)
    cfg = ec.load_config()
    cfg["decision"]["min_saving_s"] = 10_000.0
    table = ec.build({"c1": 3.0}, "congestion_level_0_3", cmap, grid, 15, cfg, hops=2)
    cur = ["A0A1", "A1A2", "A2A3", "A3A4", "A4A5", "A5B5", "B5C5", "C5D5", "D5E5"]
    trips = [{"id": "v1", "from": cur[0], "to": cur[-1], "depart": 0.0, "current_route": cur}]
    rec = ro.optimize(grid, trips, table, tmp_path / "o", seed=7, window_s=1800, cfg=cfg)
    d = rec["decisions"][0]
    assert d["decision"] in ("KEEP_CURRENT_BELOW_THRESHOLD", "NO_ALTERNATIVE")
    assert d["threshold_s"] == 10_000.0 and d["selected"] == "v1_c0"
    if d["decision"] == "KEEP_CURRENT_BELOW_THRESHOLD":
        assert d["current_future_cost_s"] is not None and d["alternative_future_cost_s"] is not None and "predicted_saving_s" in d


@needs_sumo
def test_capacity_and_share_gates_reject_herding(grid, tmp_path):
    cmap = {"c1": {"edges": ["B0C0", "C0D0", "D0E0"]}}                             # a slowed corridor along row 0
    cfg = ec.load_config()
    cfg["decision"]["min_saving_s"] = 0.0; cfg["decision"]["min_saving_pct"] = 0.0
    cfg["generalized_cost"]["load_penalty"]["capacity_veh_per_lane_h"] = 4.0     # 2 vehicles per edge in a 30-min window
    cfg["admission"]["max_share_per_alternative"] = 1.0
    table = ec.build({"c1": 3.0}, "congestion_level_0_3", cmap, grid, 15, cfg, hops=1)
    cur = ["A0B0", "B0C0", "C0D0", "D0E0", "E0E1", "E1E2", "E2E3", "E3E4", "E4E5"]       # through the slowed corridor
    trips = [{"id": f"v{i}", "from": cur[0], "to": cur[-1], "depart": float(i), "current_route": cur} for i in range(8)]
    rec = ro.optimize(grid, trips, table, tmp_path / "cap", seed=3, window_s=1800, cfg=cfg)
    s = rec["stats"]
    assert s["rejected_by_capacity_gate"] > 0, s
    assert s["vehicles_admitted"] + s["rejected_by_capacity_gate"] + s["rejected_by_share_gate"] + s["decisions"].get("KEEP_CURRENT_BELOW_THRESHOLD", 0) \
        + s["decisions"].get("NO_ALTERNATIVE", 0) == 8
    cfg["generalized_cost"]["load_penalty"]["capacity_veh_per_lane_h"] = 1e6
    cfg["admission"]["max_share_per_alternative"] = 0.25
    rec2 = ro.optimize(grid, trips, table, tmp_path / "share", seed=3, window_s=1800, cfg=cfg)
    assert rec2["stats"]["rejected_by_share_gate"] > 0
    assert rec2["stats"]["top_route_share"] <= 0.25 + 1e-9
    for k in ("top_route_share", "top_edge_flow_concentration", "vehicles_admitted", "rejected_by_capacity_gate", "reroute_count"):
        assert k in rec2["stats"]


def test_config_has_no_unexplained_constants():
    cfg = json.loads(ec.CONFIG_FILE.read_text())
    for section in ("edge_costs", "candidates", "generalized_cost", "decision", "admission"):
        assert section in cfg
    assert cfg["generalized_cost"]["load_penalty"]["_source"] and cfg["generalized_cost"]["_rule"] and cfg["decision"]["_rule"]
