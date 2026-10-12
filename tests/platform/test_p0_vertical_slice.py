"""P0 vertical-slice tests: routing graph, alternatives, and the honesty gates.

The gates matter more than the happy paths. Each one here corresponds to a real
failure this slice actually produced during P0 and would otherwise have reported
as a clean result.
"""
from __future__ import annotations

import pytest

from core.common.city import DHAKA_R1, CityProfile, TrafficSide, get_city
from core.simulation.twin.sumo_runner import (CounterfactualComparison,
                                                DemandCompletion, write_route_file)
from core.common.types import TrafficMetrics
from core.simulation.routing.graph_router import (EdgeInfo, NetworkGraph, RouteDistribution,
                                            RouteUnreachable, candidate_distributions,
                                            diverse_alternatives, _edge_overlap)


# ------------------------------------------------------------------ city
def test_city_requires_explicit_signal_timing_provenance():
    """An unlabelled timing source silently becomes a false realism claim."""
    with pytest.raises(ValueError, match="signal_timing_provenance"):
        CityProfile(city_id="x", display_name="X", country="Y",
                    network_path=DHAKA_R1.network_path, traffic_side=TrafficSide.LEFT)


def test_dhaka_profile_is_left_hand_and_labels_heuristic_timings():
    c = get_city("dhaka_r1")
    assert c.is_left_hand
    assert c.signal_timing_provenance == "IMPORTED_HEURISTIC"
    assert c.demand_provenance == "SYNTHETIC_VALIDATION_DEMAND"


@pytest.mark.skipif(not DHAKA_R1.network_path.exists(), reason="frozen network absent")
def test_frozen_network_checksum_matches():
    ok, actual = DHAKA_R1.verify_network()
    assert ok, f"network checksum drifted: {actual}"


# --------------------------------------------------------------- graph
def _toy_graph() -> NetworkGraph:
    #   A ──► B ──► D        (fast, direct)
    #   A ──► C ──► D        (slow detour, fully disjoint in the middle)
    e = {
        "A": EdgeInfo("A", 100.0, 10.0, 1, "n1", "n0"),
        "B": EdgeInfo("B", 100.0, 10.0, 1, "n2", "n1"),
        "C": EdgeInfo("C", 300.0, 10.0, 1, "n2", "n1"),
        "D": EdgeInfo("D", 100.0, 10.0, 1, "n3", "n2"),
    }
    succ = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
    return NetworkGraph(e, succ)


def test_shortest_path_prefers_the_cheaper_branch():
    g = _toy_graph()
    path, cost, _ = g.shortest_path("A", "D", lambda e, t=0.0: g.edge(e).free_flow_time_s)
    assert path == ["A", "B", "D"]
    assert cost == pytest.approx(30.0)


def test_unreachable_returns_empty_not_a_fake_route():
    g = _toy_graph()
    path, cost, _ = g.shortest_path("D", "A", lambda e, t=0.0: 1.0)
    assert path == [] and cost == float("inf")


def test_diverse_alternatives_finds_the_disjoint_detour():
    g = _toy_graph()
    alts = diverse_alternatives(g, "A", "D",
                                lambda e, t=0.0: g.edge(e).free_flow_time_s,
                                k=2, max_overlap=0.9)
    assert len(alts) == 2
    assert alts[0][0] == ["A", "B", "D"]
    assert "C" in alts[1][0], "penalty method must push the second path onto a different road"


def test_edge_overlap_is_symmetric_and_bounded():
    assert _edge_overlap(["a", "b"], ["a", "b"]) == 1.0
    assert _edge_overlap(["a"], ["b"]) == 0.0
    assert 0.0 <= _edge_overlap(["a", "b", "c"], ["b", "c", "d"]) <= 1.0


# -------------------------------------------------------- distributions
def test_shares_must_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1.0"):
        RouteDistribution(label="bad", paths=[["a"], ["b"]], shares=[0.5, 0.2])


def test_assign_preserves_the_vehicle_total_exactly():
    d = RouteDistribution(label="d", paths=[["a"], ["b"], ["c"]],
                          shares=[0.55, 0.25, 0.20])
    counts = d.assign(101)
    assert sum(counts) == 101, "rounding must never lose or invent vehicles"


def test_candidate_set_includes_every_pure_strategy_and_an_even_split():
    dists = candidate_distributions([["a"], ["b"], ["c"]])
    labels = {d.label for d in dists}
    assert {"all_path_0", "all_path_1", "all_path_2", "even_split"} <= labels


# ------------------------------------------------- honesty gates (the point)
def test_demand_completion_flags_an_insertion_backlog():
    """The P0 bug: 2000 of 2500 vehicles never entered, yet trips looked fine."""
    d = DemandCompletion(loaded=2500, inserted=500, running_at_end=157,
                         waiting_at_end=2000)
    assert not d.is_complete
    assert d.insertion_rate == pytest.approx(0.2)


def test_demand_completion_requires_everything_to_finish():
    assert DemandCompletion(loaded=10, inserted=10, running_at_end=0,
                            waiting_at_end=0).is_complete
    # still running at the horizon ⇒ statistics cover only part of the demand
    assert not DemandCompletion(loaded=10, inserted=10, running_at_end=3,
                                waiting_at_end=0).is_complete


def test_counterfactual_reports_none_when_a_metric_is_missing():
    """A missing metric must never be silently treated as zero."""
    base = TrafficMetrics(scenario_id="s", seed=1, avg_time_loss_s=100.0)
    interv = TrafficMetrics(scenario_id="s", seed=1, avg_time_loss_s=None)
    c = CounterfactualComparison(base, interv, seed=1, intervention_label="x")
    assert c.delta("avg_time_loss_s") is None
    assert c.percent_change("avg_time_loss_s") is None


def test_counterfactual_percent_change_direction():
    base = TrafficMetrics(scenario_id="s", seed=1, avg_time_loss_s=200.0)
    interv = TrafficMetrics(scenario_id="s", seed=1, avg_time_loss_s=150.0)
    c = CounterfactualComparison(base, interv, seed=1, intervention_label="x")
    assert c.percent_change("avg_time_loss_s") == pytest.approx(-25.0)
    assert c.both_runs_clean


def test_route_file_writes_every_requested_vehicle(tmp_path):
    p = write_route_file(tmp_path / "r.rou.xml",
                         {"r0": ["a", "b"], "r1": ["c"]},
                         {"r0": 3, "r1": 2}, depart_span_s=10.0)
    text = p.read_text()
    assert text.count("<vehicle ") == 5
    assert '<route id="r0" edges="a b"/>' in text
