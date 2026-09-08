"""Time-dependent route costing, the statistical incident detector and the online residual correction."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.routing import edge_costs as ec                                   # noqa: E402
from pipeline.routing import route_optimizer as ro                              # noqa: E402
from pipeline.v2x.state_correction import IncidentDetector, residual_correction  # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("netgenerate") is None, reason="SUMO binaries not installed")


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    d = tmp_path_factory.mktemp("sc"); net = d / "g.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", "5", "--grid.length", "600", "--default.speed", "20", "--default.lanenumber", "1", "--no-turnarounds", "-o", str(net)], check=True, capture_output=True)
    return net


@needs_sumo
def test_time_dependent_costing_prices_each_edge_at_its_entry_time(grid):
    info = ro.NetInfo(grid)
    route = ["A0B0", "B0C0", "C0D0", "D0E0"]                        # 4 × 600 m at 20 m/s = 30 s each at free flow
    free = info.free_tt["A0B0"]
    # D0E0 is slow ONLY at +30 min; everything else free-flow. Departing now, the vehicle reaches D0E0 after ~90 s → horizon ~1.5 min → almost the "now" price.
    td = ro.TimeDependentCosts({0: {}, 15: {}, 30: {"D0E0": 300.0}})
    now_cost = ro.route_terms(route, td, info)["forecast_future_tt_s"]
    assert now_cost == pytest.approx(4 * free, rel=0.02)                                     # D0E0 is entered at ~1.5 min: between the "now" and +15 tables, both free-flow — the +30 slowdown does not leak
    later = ro.route_terms(route, td, info, depart_offset_s=28 * 60)["forecast_future_tt_s"]   # departing at +28 min: D0E0 entered at ~+29.5 min → almost fully slow (interpolated between +15 free and +30 slow)
    assert later > 3 * free + 250
    assert td.at("D0E0", 22.5, free) == pytest.approx(free + (300 - free) * 0.5) and td.at("D0E0", 45, free) == 300.0 and td.at("Z9", 10, free) is None
    assert td.at("D0E0", 10, free) is None                                                   # unpriced at every horizon below +30: the caller falls back to free flow
    plain = ro.route_terms(route, {"D0E0": 300.0}, info)["forecast_future_tt_s"]
    assert plain == pytest.approx(3 * free + 300.0, rel=0.01) and not ro.route_terms(route, {"D0E0": 300.0}, info)["time_dependent"]


def test_incident_detector_needs_several_vehicles_and_messages_and_reports_delay():
    det = IncidentDetector(window_s=60, min_vehicles=3, min_messages=5, ratio=0.5)
    for t in range(0, 40, 10):
        det.ingest(t, "E1", "v1", 2.0, 20.0)                        # one vehicle crawling is not an incident
    assert det.detect(40, {"E1": 0}) == []
    det.ingest(41, "E1", "v2", 3.0, 20.0); det.ingest(42, "E1", "v3", 1.0, 20.0)
    new = det.detect(42, {"E1": 0})
    assert len(new) == 1 and new[0]["edge"] == "E1" and new[0]["vehicles"] == 3 and new[0]["messages"] >= 5
    assert 0.8 <= new[0]["severity"] <= 0.95 and new[0]["detection_delay_s"] == 42.0
    assert det.detect(43, {"E1": 0}) == []                          # already active: not reported twice
    det2 = IncidentDetector(); [det2.ingest(t, "E2", f"v{t}", 19.0, 20.0) for t in range(10)]
    assert det2.detect(10) == []                                    # fast traffic is never an incident


@needs_sumo
def test_residual_correction_decays_with_horizon_propagates_upstream_only_and_never_speeds_up(grid):
    import sumolib
    net = sumolib.net.readNet(str(grid)); cfg = ec.load_config()
    cmap = {"c": {"edges": ["C0D0"]}}
    base = {h: ec.build({"c": 18.0}, "speed_mps", cmap, grid, h or 15, cfg, hops=0, model="t", corridor_free_speed={"c": 20.0}) for h in (0, 15, 30, 60)}
    corrected, diag = residual_correction(base, {"C0D0": 4.0, "A0B0": 20.0}, net, cfg, tau_min=30.0, upstream_hops=1, hop_decay=0.5)
    r0, r30, r60 = (corrected[h]["edges"]["C0D0"] for h in (0, 30, 60))
    assert r0["source"] == "OBSERVED" and r0["bounded_speed_mps"] == pytest.approx(4.0, abs=0.01)
    assert r0["bounded_speed_mps"] < r30["bounded_speed_mps"] < r60["bounded_speed_mps"] < 18.0      # the correction fades with horizon
    assert "B0C0" in corrected[0]["edges"] and corrected[0]["edges"]["B0C0"]["source"] == "RESIDUAL_UPSTREAM" and corrected[0]["edges"]["B0C0"]["upstream_hop"] == 1
    assert "D0E0" not in corrected[0]["edges"]                                                        # downstream untouched
    assert "A0B0" not in corrected[0]["edges"] and diag["residual_edges"] == 1                         # free-flow observation: no residual
    assert corrected[0]["future_cost_hash"] != base[0]["future_cost_hash"] and corrected[0]["forecast_only_cost_hash"] == base[0]["future_cost_hash"]
    same, d2 = residual_correction(base, {"C0D0": 19.5}, net, cfg)                                    # faster than expected: never applied
    assert d2["residual_edges"] == 0 and same[0]["future_cost_hash"] == base[0]["future_cost_hash"]


def test_controller_gate_is_computed_not_declared():
    from pipeline.v2x.controller_gate import gate
    st = lambda mean, lo, hi, label, w=3, l=0: {"mean_pct": mean, "ci95": [lo, hi], "wins": w, "losses": l, "ties": 0, "label": label, "seeds": 3}
    good = {"seeds": [201, 202, 203], "reroutes_by_arm": {"x": 40}, "fork_state_identical_across_arms": True, "protocol": {}, "run_dir": "r",
            "paired": {"x_vs_baseline": {"total_vehicle_hours_incl_never_inserted": st(-2, -3, -1, "HELPED"), "teleports": st(0, -1, 1, "INCONCLUSIVE")}, "x_vs_reactive": {"total_vehicle_hours_incl_never_inserted": st(-1, -2, -0.5, "HELPED")}}}
    assert gate(good, "x")["status"] == "TRAFFIC_BENEFIT_ESTABLISHED"
    dev = {**good, "seeds": [101, 102, 103]}
    assert gate(dev, "x")["status"] == "MECHANICALLY_VALIDATED"                      # development seeds can never establish a benefit
    incon = json.loads(json.dumps(good)); incon["paired"]["x_vs_reactive"]["total_vehicle_hours_incl_never_inserted"]["label"] = "INCONCLUSIVE"
    assert gate(incon, "x")["status"] == "TRAFFIC_BENEFIT_NOT_ESTABLISHED"
    tele = json.loads(json.dumps(good)); tele["paired"]["x_vs_baseline"]["teleports"]["label"] = "HURT"
    assert gate(tele, "x")["status"] == "TRAFFIC_BENEFIT_NOT_ESTABLISHED"           # apparent benefit with worse teleports does not count
    assert gate({**good, "reroutes_by_arm": {"x": 0}}, "x")["status"] == "NOT_VALIDATED"
