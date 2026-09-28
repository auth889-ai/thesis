"""The learned-model outcome gate: frozen protocol identity, held-out moments, measured speed caps,
the outcome classes, and the read-only endpoint — without SUMO runs or checkpoints."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src/dashboard/backend"))

from pipeline.routing import learned_gate as lg  # noqa: E402

MAPPING = REPO / "data/cities/los_angeles_metr/sumo/sensor_to_edge.json"
CKPT = REPO / "results/forecasting/checkpoints_cloud/city-user-los-angeles-gwnet"
needs_la = pytest.mark.skipif(not (MAPPING.exists() and CKPT.exists()), reason="LA scenario / Graph WaveNet checkpoint not present here")


def test_moment_is_inside_the_held_out_split_with_room_for_input_and_future():
    T = 4032
    from pipeline.forecasting import train_eval as te
    lo = te.splits(T)["test"][0]
    seen = set()
    for seed in list(range(301, 321)) + [101, 102, 103]:
        m = lg.moment_for_seed({}, seed, T)
        assert lo + 12 <= m <= T - 12, (seed, m)
        seen.add(m)
    assert len(seen) >= 20                                     # distinct moments, not one repeated


def test_speed_caps_never_exceed_the_limit_and_fall_back_to_it_when_unmeasured():
    mapping = {"records": [{"node": "n1", "quality": "GOOD", "edge": "e1", "sensor_id": "1", "speed_limit_mps": 20.0, "lat": 0, "lon": 0, "snap_m": 1, "edge_type": "highway.motorway", "edge_length_m": 100, "opposite_edge": None}]}
    actual = np.full((12, 1), np.nan); actual[0, 0] = 36.0; actual[1, 0] = 90.0; actual[2, 0] = 0.0
    F = {"nodes": ["n1"], "actual": actual, "unit": "speed km/h"}
    sched = lg.speed_schedule(F, mapping, {"simulation_duration_s": 900})
    assert sched == {"e1": [(0, 10.0), (300, 20.0), (600, 20.0)]}


def _rec(seed, base, react, pers, learn, oracle=None, skill=0.2):
    def arm(v, changed=1):
        return {"metrics": {"total_vehicle_hours_incl_never_inserted": v, "total_vehicle_hours": v, "mean_travel_time_all": v, "mean_travel_time_s": v, "p95_travel_time_s": v, "total_waiting_s": v, "mean_queue_veh": v, "max_queue_veh": v,
                            "arrived": 100, "teleports": 0, "top_route_share": 0.1, "top_edge_flow_concentration": 0.1, "teleport_events": [], "teleport_rate_per_1000_inserted": 0.0, "teleport_edges": {}, "probe": {}},
                "routing": {"mean_predicted_saving_s": 10.0, "routes_changed": changed}, "decisions": {}}
    arms = {"baseline": arm(base), "reactive": arm(react), "persistence_predictive": arm(pers), "learned_predictive": arm(learn)}
    if oracle is not None:
        arms["oracle"] = arm(oracle)
    return {"seed": seed, "arms": arms, "same_population": True,
            "quality_vs_outcome": {"skill_vs_persistence": skill, "realized_saving_pct_learned_vs_baseline": 100 * (base - learn) / base, "realized_saving_pct_persistence_vs_baseline": 100 * (base - pers) / base}}


def _P(with_oracle=False):
    return {"primary_metric_key": "total_vehicle_hours_incl_never_inserted", "with_oracle": with_oracle, "protocol_id": "T"}


def test_outcome_a_when_learned_beats_both_baseline_and_persistence():
    recs = [_rec(s, 100, 101, 99, 95 + 0.1 * s) for s in range(10)]
    rep = lg.report(_P(), recs, "t")
    assert rep["verdict"] == "HELPED" and rep["learned_vs_persistence"]["label"] == "HELPED" and rep["outcome"].startswith("A")
    assert rep["persistence_vs_baseline"]["label"] == "HELPED" and "oracle_vs_baseline" not in rep["paired"]


def test_outcome_b_when_only_baseline_is_beaten_and_d_when_learned_hurts():
    recs = [_rec(s, 100, 101, 96, 96) for s in range(10)]
    assert lg.report(_P(), recs, "t")["outcome"].startswith("B")
    recs = [_rec(s, 100, 101, 100, 104 + 0.1 * s) for s in range(10)]
    rep = lg.report(_P(), recs, "t")
    assert rep["verdict"] == "HURT" and rep["outcome"].startswith("D")


def test_outcome_c_when_nothing_is_established_and_oracle_stays_out_of_the_headline():
    recs = [_rec(s, 100, 100.5, 100 + (-1) ** s, 100 - (-1) ** s, oracle=90) for s in range(10)]
    rep = lg.report(_P(True), recs, "t")
    assert rep["verdict"] == "INCONCLUSIVE" and rep["outcome"].startswith("C")
    assert rep["paired"]["oracle_vs_baseline"]["total_vehicle_hours_incl_never_inserted"]["label"] == "HELPED"
    assert rep["primary"]["pair"] == "learned_predictive vs baseline"          # the headline never uses the oracle
    md = lg.markdown({**rep, "protocol": {**rep["protocol"], **{k: "x" for k in ("city_id", "network_hash", "dataset", "dataset_hash", "mapping_hash", "mapping_counts", "model", "checkpoint", "checkpoint_sha256", "held_out_skill", "routing_config_hash", "coverage_hops", "min_saving_s", "min_saving_pct", "demand_method", "calibration_method", "simulation_duration_s", "routing_round_s", "round_horizons_min", "compliance", "forecast_moments", "sumo_version", "dev_seeds", "final_seeds")}}})
    assert "INCONCLUSIVE" in md and "Teleports" in md


def test_spearman_is_rank_based():
    assert lg.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert lg.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0
    assert lg.spearman([1, 2], [1, 2]) is None


@needs_la
def test_protocol_freezes_the_validated_checkpoint_and_the_mapping():
    P = lg.protocol()
    assert P["protocol_id"] == "FINAL_LEARNED_PROTOCOL_v1" and P["model"] == "GWNet"
    assert P["checkpoint_sha256"] == lg.FROZEN_SHA and P["training_job_id"] == lg.FROZEN_JOB and P["checkpoint_epochs"] == 120
    card = json.loads((REPO / P["frozen_card"]).read_text())
    assert card["checkpoint"] == P["checkpoint_path"] and card["checkpoint_sha256"] == lg.FROZEN_SHA   # pinned by job + SHA, not by today's registry
    assert P["mapping_counts"]["GOOD"] >= 6
    assert len(P["final_seeds"]) >= 10 and not set(P["dev_seeds"]) & set(P["final_seeds"])
    assert P["compliance"] == 0.3 and P["routing_round_s"] == 900 and P["primary_metric_key"] == "total_vehicle_hours_incl_never_inserted"
