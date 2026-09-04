"""The forecast -> future edge cost -> chain-service seam.

These cover the pieces that make the chain runnable as one command: the as-of cut on the recorded
window (a model must never see past the moment it forecasts from), the two pricing rules, and the
run record's shape. They deliberately do not run SUMO or a model — the chain command itself is the
end-to-end check.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.routing import forecast_to_costs as fc            # noqa: E402
from pipeline.routing import integrated_chain as ic             # noqa: E402

VALS = np.array([[0.0, 1.0], [np.nan, 2.0], [3.0, np.nan], [1.0, 1.0]])
MASK = ~np.isnan(VALS)
BINS = np.array([0.0, 300.0, 600.0, 900.0])


def test_as_of_latest_is_the_last_observed_bin():
    assert fc.resolve_as_of("latest", VALS, MASK, BINS) == 3


def test_as_of_peak_is_the_busiest_observed_bin():
    assert fc.resolve_as_of("peak", VALS, MASK, BINS) == 2


def test_as_of_accepts_an_index_and_a_timestamp():
    assert fc.resolve_as_of("1", VALS, MASK, BINS) == 1
    assert fc.resolve_as_of("1970-01-01T00:10:00+00:00", VALS, MASK, BINS) == 2


def test_observed_levels_carry_the_last_reading_forward_with_its_age():
    levels, ages = fc.observed_levels(VALS, MASK, BINS, 2)
    assert levels == {0: 3.0, 1: 2.0}
    assert ages == {0: 0, 1: 1}          # node 1 was not observed at bin 2


def test_congestion_classes_are_priced_by_band_midpoint_not_by_a_fake_speed():
    cmap = {"c1": {"edges": ["e1", "e2"], "edge_free_tt_s": {"e1": 10.0, "e2": 20.0}}}
    f = {"values": {15: [2.0]}, "node_ids": ["c1"], "unit": fc.LEVEL_UNIT}
    tt, covered, pricing = fc._price_from_levels(f, 15, cmap)
    assert covered == {"e1", "e2"}
    assert tt == {"e1": 17.5, "e2": 35.0}          # CONGESTED -> x1.75
    assert pricing["band_midpoints"][2] == 1.75


def test_a_shared_edge_takes_the_worst_corridor():
    cmap = {"a": {"edges": ["e1"], "edge_free_tt_s": {"e1": 10.0}},
            "b": {"edges": ["e1"], "edge_free_tt_s": {"e1": 10.0}}}
    f = {"values": {15: [0.0, 3.0]}, "node_ids": ["a", "b"], "unit": fc.LEVEL_UNIT}
    tt, _, _ = fc._price_from_levels(f, 15, cmap)
    assert tt["e1"] == 25.0                        # SEVERE x2.5 wins over FREE_FLOW x1.08


def test_an_unforecast_corridor_is_left_uncovered_rather_than_invented():
    cmap = {"a": {"edges": ["e1"], "edge_free_tt_s": {"e1": 10.0}},
            "b": {"edges": ["e2"], "edge_free_tt_s": {"e2": 10.0}}}
    f = {"values": {15: [1.0, float("nan")]}, "node_ids": ["a", "b"], "unit": fc.LEVEL_UNIT}
    tt, covered, _ = fc._price_from_levels(f, 15, cmap)
    assert covered == {"e1"} and "e2" not in tt


def test_scenario_levels_come_from_the_observation_the_forecast_was_made_from():
    res = {"observed": {"levels": {"karwanbazar_to_shahbagh": 3.0}}}
    levels, why = ic.scenario_levels("observed", res)
    assert levels == {"karwanbazar_to_shahbagh": 3.0} and "REAL_LIVE" in why


def test_explicit_levels_are_labelled_a_stated_counterfactual():
    levels, why = ic.scenario_levels("a=3,b=2", {})
    assert levels == {"a": 3.0, "b": 2.0} and "COUNTERFACTUAL" in why


def test_observed_levels_refuse_a_source_that_cannot_supply_them():
    with pytest.raises(SystemExit):
        ic.scenario_levels("observed", {"forecast": {}})


def test_every_run_id_is_unique_and_sortable():
    ids = [ic.new_run_id("smoke") for _ in range(5)]
    assert len(set(ids)) == 5
    assert all(i.startswith("chain_") and "_smoke_" in i for i in ids)


def test_the_arms_are_the_three_the_comparison_needs():
    assert ic.ARMS == ("baseline", "reactive", "prediction_aware")


def test_summarise_reports_every_measured_metric_per_arm():
    def run(arm, seed, vh, q):
        return {"arm": arm, "seed": seed, "routes_changed": 1, "advisories_delivered": 2,
                "metrics": {"total_vehicle_hours": vh, "mean_travel_time_s": 300.0,
                            "p95_travel_time_s": 500.0, "total_waiting_s": 1000.0,
                            "mean_time_loss_s": 50.0, "mean_queue_veh": q, "max_queue_veh": q * 2,
                            "arrived": 100, "teleports": 0}}
    s = ic.summarise([run("baseline", 11, 100.0, 10.0), run("reactive", 11, 90.0, 9.0),
                      run("prediction_aware", 11, 80.0, 8.0),
                      run("baseline", 12, 100.0, 10.0), run("reactive", 12, 110.0, 11.0),
                      run("prediction_aware", 12, 80.0, 8.0)])
    rows = {r["arm"]: r for r in s["arms"]}
    assert set(rows) == set(ic.ARMS)
    for k in ("total_vehicle_hours", "mean_travel_time_s", "p95_travel_time_s", "total_waiting_s",
              "mean_queue_veh", "arrived", "teleports", "reroutes"):
        assert k in rows["baseline"], k
    # a mean the seeds disagree on is not a result
    assert s["verdict"]["reactive"]["claim"] == "NOT_ESTABLISHED"
    assert s["verdict"]["prediction_aware"]["claim"] == "IMPROVES"


def test_the_smoke_run_record_holds_measured_outputs():
    """If a chain run exists in this checkout, it must carry real per-arm metrics."""
    latest = ic.RUNS / "LATEST"
    if not latest.exists():
        pytest.skip("no chain run in this checkout")
    rec = ic.json.loads((ic.RUNS / latest.read_text().strip() / "run.json").read_text())
    assert rec["forecast"]["model"] and rec["coverage"]["covered"] > 0
    assert {r["arm"] for r in rec["runs"]} == set(ic.ARMS)
    for r in rec["runs"]:
        m = r["metrics"]
        assert m["total_vehicle_hours"] > 0 and m["arrived"] > 0
        assert m["mean_queue_veh"] is not None
        assert (REPO / r["out_dir"] / "tripinfo.xml").exists()
