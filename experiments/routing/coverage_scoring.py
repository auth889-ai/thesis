"""Score retained same-state decisions on matched edge and route populations."""
import gzip
import json
from collections import Counter
from itertools import combinations

from experiments.routing.coverage_analysis import Errors
from pipeline.routing import route_optimizer as ro


def route_stratum(labels):
    kinds = set(labels)
    if kinds == {"UNPRICED"}:
        return "ZERO_COVERAGE"
    if "UNPRICED" in kinds:
        return "PARTIAL_COVERAGE"
    return "DIRECT_ONLY" if kinds == {"DIRECT"} else "DERIVED_ONLY" if kinds == {"DERIVED"} else "DIRECT_AND_DERIVED"


def score_retained_round(root, info):
    tables = json.loads((root / "cost_tables.json").read_text())
    sources, labels = tables["sources"], tables["edge_labels"]
    edge_errors = {s: {k: Errors() for k in ("DIRECT", "DERIVED", "UNPRICED")} for s in ("gwnet", "persistence")}
    route_errors = {s: {} for s in edge_errors}
    ranks = {s: {} for s in edge_errors}
    candidates = Counter()
    missed_causes = Counter()
    candidate_gap, within_set_regret = Errors(), Errors()
    used = set()
    with gzip.open(root / "vehicle_decisions.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            paths = row["candidates"]
            used.update(e for p in paths for e in p["edges"])
            if row["admission_result"]["oracle"] == "REROUTE":
                if row["admission_result"].get("gwnet") != "REROUTE":
                    missed_causes[row.get("primary_failure_cause") or "UNCLASSIFIED"] += 1
                own_hashes = set(row["source_candidate_hashes"]["gwnet"])
                own = [p for p in paths if p["path_hash"] in own_hashes]
                current = next(p for p in paths if p["edges"] == row["current_route_edges"])
                chosen = next(p for p in paths if p["edges"] == row["selected_route"]["gwnet"])
                oracle_chosen = next(p for p in paths if p["edges"] == row["selected_route"]["oracle"])
                best_own = min(p["cost_s"]["oracle"] for p in own)
                candidates["oracle_admitted_opportunities"] += 1
                candidates["exact_oracle_path_in_gwnet_set"] += int(oracle_chosen["path_hash"] in own_hashes)
                candidates["any_oracle_cheaper_path_in_gwnet_set"] += int(best_own < current["cost_s"]["oracle"] - 1e-9)
                candidates["gwnet_advised_action_is_oracle_best_in_own_set"] += int(abs(chosen["cost_s"]["oracle"] - best_own) < 1e-9)
                candidate_gap.add(best_own - min(p["cost_s"]["oracle"] for p in paths))
                within_set_regret.add(chosen["cost_s"]["oracle"] - best_own)
            for s in edge_errors:
                for p in paths:
                    group = route_stratum(p["edge_labels"])
                    route_errors[s].setdefault(group, Errors()).add(p["cost_s"][s] - p["cost_s"]["oracle"])
                for a, b in combinations(paths, 2):
                    group = route_stratum(a["edge_labels"] + b["edge_labels"])
                    stat = ranks[s].setdefault(group, Counter())
                    od = a["cost_s"]["oracle"] - b["cost_s"]["oracle"]
                    sd = a["cost_s"][s] - b["cost_s"][s]
                    stat["pairs"] += 1
                    stat["agreements"] += int((od > 0) - (od < 0) == (sd > 0) - (sd < 0))
    oracle = sources["oracle"]["edge_travel_times"]
    for e in used & oracle.keys():
        kind = labels.get(e, "UNPRICED")
        for s in edge_errors:
            value = sources[s]["edge_travel_times"].get(e, info.free_tt.get(e, 0))
            edge_errors[s][kind].add(value - oracle[e])
    return {"schema_version": 2,
            "missed_oracle_no_gwnet_reroute_causes": dict(missed_causes),
            "matched_edge_time_error_s": {s: {k: v.result() for k, v in groups.items()} for s, groups in edge_errors.items()},
            "route_cost_error_by_coverage_s": {s: {k: v.result() for k, v in groups.items()} for s, groups in route_errors.items()},
            "pairwise_ranking_by_coverage": {s: {k: dict(v) for k, v in groups.items()} for s, groups in ranks.items()},
            "candidate_set_diagnostics": {"counts": dict(candidates), "best_own_vs_best_union_oracle_cost_gap_s": candidate_gap.result(),
                "advised_action_vs_best_own_oracle_cost_regret_s": within_set_regret.result(),
                "scope": "Oracle-admitted shadow opportunities. Any-cheaper does not mean admission-qualified. Regret includes admission effects; values are cost-policy estimates, not achieved vehicle-hour effects."},
            "scope": "Both sources use the same GWNet coverage labels and oracle-observed candidate edges. UNPRICED is fallback error, not DL forecast error. Edge errors use frozen 15-minute cost tables; route costs use each source's frozen horizon handling. Oracle truth is a baseline future-window estimate, not observed counterfactual route travel time."}


def score_all(folder, rounds, network):
    info = None
    results = []
    for row in rounds:
        root = folder / f"audit/s{row['seed']}/round_{row['round']}"
        path = root / "matched_scoring.json"
        if path.exists() and json.loads(path.read_text()).get("schema_version") == 2:
            value = json.loads(path.read_text())
        else:
            if info is None:
                info = ro.NetInfo(network)
            value = score_retained_round(root, info)
            path.write_text(json.dumps(value, indent=2))
        results.append(value)
    return results
