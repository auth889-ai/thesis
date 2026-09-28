"""Guard the information-only intervention and the route comparison denominator."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from traffictwin.coverage import intervene
from experiments.routing.coverage_analysis import primary_cause, priced_stats, path_key


def fixture_table():
    return {"edge_travel_times": {"d": 10, "p": 20}, "edges": {"d": {"source": "DIRECT"}, "p": {"source": "DERIVED"}},
            "time_dependent": {0: {"d": 8, "p": 17}, 15: {"d": 10, "p": 20}}}


def test_oracle_cannot_expand_coverage_or_invent_unobserved_values():
    table = fixture_table(); before = copy.deepcopy(table)
    result = intervene(table, "oracle_coverage_limited", {"edge_travel_times": {"d": 15, "outside": 100}})
    assert result["edge_travel_times"] == {"d": 15, "p": 20}
    assert result["time_dependent"][0] == {"d": 15, "p": 17}
    assert result["oracle_unobserved_covered_edges"] == ["p"]
    assert table == before


def test_direct_only_removes_derived_from_every_horizon():
    result = intervene(fixture_table(), "gwnet_direct")
    assert result["direct_edges"] == 1 and result["derived_edges"] == 0
    assert all(set(v) == {"d"} for v in result["time_dependent"].values())


def test_coverage_path_denominators_and_exact_route_identity():
    value = priced_stats([["a", "b"], ["a"], ["c"]], {"a"})
    assert value["fully_priced_paths"] == value["partially_priced_paths"] == value["zero_coverage_paths"] == 1
    assert value["priced_edge_pct"] == 50
    assert path_key(["a", "b"]) != path_key(["b", "a"])


def test_primary_cause_is_exclusive_for_missing_candidate_and_admission():
    assert primary_cause(["b"], ["a"], [["a"]], "NO_ALTERNATIVE", {}, {}, {}) == "D_CANDIDATE_MISSING"
    assert primary_cause(["b"], ["a"], [["a"], ["b"]], "REJECTED_COOLDOWN", {}, {}, {}) == "E_OPTIMIZER_REJECTION"
    assert primary_cause(["b"], ["b"], [["a"], ["b"]], "REROUTE", {}, {}, {}) == "G_NO_ACTION_DIFFERENCE"


def test_coverage_repair_requires_route_ordering_to_change():
    args = (["b"], ["a"], [["a"], ["b"]], "KEEP_CURRENT_BELOW_THRESHOLD", {"a": "UNPRICED", "b": "DIRECT"})
    assert primary_cause(*args, {"a": 30, "b": 10}, {"a": 5, "b": 10}) == "B_COVERAGE_MISSING"


def test_route_strata_do_not_call_partial_routes_direct():
    from experiments.routing.coverage_scoring import route_stratum
    assert route_stratum(["DIRECT", "UNPRICED"]) == "PARTIAL_COVERAGE"
    assert route_stratum(["UNPRICED"]) == "ZERO_COVERAGE"
    assert route_stratum(["DERIVED", "DIRECT"]) == "DIRECT_AND_DERIVED"


def test_gap_contrasts_preserve_negative_contributions():
    from experiments.routing.coverage_report import effect_partition, KEY
    values = {"oracle_v2x": 80, "oracle_coverage_limited_v2x": 110, "predictive_v2x": 100}
    result = effect_partition({201: {k: {"metrics": {KEY: v}} for k, v in values.items()}})
    assert result["coverage_contrast_pct"] == 150
    assert result["forecast_value_contrast_pct"] == -50
    assert result["candidate_generation_pct"] is None


def test_matched_scoring_uses_same_edge_labels_and_separates_candidate_regret(tmp_path):
    import gzip
    import json
    from types import SimpleNamespace
    from experiments.routing.coverage_scoring import score_retained_round

    tables = {"sources": {"oracle": {"edge_travel_times": {"a": 20, "b": 5}},
                          "gwnet": {"edge_travel_times": {"a": 10, "b": 12}},
                          "persistence": {"edge_travel_times": {"a": 18}}},
              "edge_labels": {"a": "DIRECT", "b": "DERIVED"}}
    (tmp_path / "cost_tables.json").write_text(json.dumps(tables))
    paths = [{"path_hash": e, "edges": [e], "edge_labels": [tables["edge_labels"][e]],
              "cost_s": {s: data["edge_travel_times"].get(e, 4) for s, data in tables["sources"].items()}} for e in ("a", "b")]
    row = {"candidates": paths, "current_route_edges": ["a"], "selected_route": {"gwnet": ["a"], "oracle": ["b"]},
           "source_candidate_hashes": {"gwnet": ["a", "b"]}, "admission_result": {"oracle": "REROUTE", "gwnet": "KEEP_CURRENT_BELOW_THRESHOLD"},
           "primary_failure_cause": "B_COVERAGE_MISSING"}
    with gzip.open(tmp_path / "vehicle_decisions.jsonl.gz", "wt") as f:
        f.write(json.dumps(row) + "\n")
    result = score_retained_round(tmp_path, SimpleNamespace(free_tt={"b": 4}))
    assert result["matched_edge_time_error_s"]["persistence"]["DERIVED"]["MAE"] == 1
    d = result["candidate_set_diagnostics"]
    assert d["best_own_vs_best_union_oracle_cost_gap_s"]["MAE"] == 0
    assert d["advised_action_vs_best_own_oracle_cost_regret_s"]["MAE"] == 15
    assert d["counts"]["any_oracle_cheaper_path_in_gwnet_set"] == 1
    assert result["missed_oracle_no_gwnet_reroute_causes"] == {"B_COVERAGE_MISSING": 1}
