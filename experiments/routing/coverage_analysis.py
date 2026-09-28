#!/usr/bin/env python3
"""Same-state routing and observability audit. No controller parameters are fitted."""
import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]
from pipeline.v2x import closed_loop as cl
from pipeline.routing import route_optimizer as ro, edge_costs as ec
from experiments.routing.coverage_diagnostic import REFERENCE, read
from traffictwin.coverage import intervene

SOURCES = ("oracle", "gwnet", "persistence")
CAUSES = ("A_FORECAST_ERROR", "B_COVERAGE_MISSING", "C_DERIVATION_ERROR", "D_CANDIDATE_MISSING", "E_OPTIMIZER_REJECTION", "F_V2X_FAILURE", "G_NO_ACTION_DIFFERENCE")


class Errors:
    def __init__(self):
        self.n = 0; self.total = self.absolute = self.squared = 0.0

    def add(self, value):
        self.n += 1; self.total += value; self.absolute += abs(value); self.squared += value * value

    def result(self):
        return {"n": self.n, "MAE": self.absolute / self.n if self.n else None,
                "RMSE": math.sqrt(self.squared / self.n) if self.n else None,
                "signed_bias": self.total / self.n if self.n else None}


def path_key(edges):
    return hashlib.sha256(" ".join(edges).encode()).hexdigest()


def priced_stats(paths, mask):
    occurrences = [e for path in paths for e in path]
    unique = set(occurrences)
    covered = sum(e in mask for e in occurrences)
    return {"routes": len(paths), "edge_occurrences": len(occurrences), "priced_occurrences": covered,
            "priced_edge_pct": 100 * covered / len(occurrences) if occurrences else None,
            "unique_edges": len(unique), "unique_priced_edges": len(unique & mask),
            "fully_priced_paths": sum(bool(p) and all(e in mask for e in p) for p in paths),
            "zero_coverage_paths": sum(bool(p) and all(e not in mask for e in p) for p in paths),
            "partially_priced_paths": sum(any(e in mask for e in p) and any(e not in mask for e in p) for p in paths)}


def costs(table):
    return ro.TimeDependentCosts(table["time_dependent"]) if table.get("time_dependent") else table["edge_travel_times"]


def decide_on_candidates(trips, candidates, table, info, cfg, P, t):
    admission = ro.Admission(cfg, info, P["round_s"], len(trips))
    decisions = {trip["id"]: ro.decide_vehicle(trip["id"], candidates[trip["id"]], costs(table), info, cfg, admission, None, t)
                 for trip in trips}
    budget = max(P["controller"]["admission"]["min_reroutes_per_round"], math.ceil(P["controller"]["admission"]["max_reroute_fraction_per_round"] * len(trips)))
    ranked = sorted((d for d in decisions.values() if d["decision"] == "REROUTE"), key=lambda d: -(d.get("predicted_saving_s") or 0))
    for d in decisions.values():
        d["pre_budget_decision"] = d["decision"]
    for d in ranked[budget:]:
        d["decision"] = "DEFERRED_BUDGET"
    return decisions


def selected(d):
    c = next((c for c in d["candidates"] if c["route_id"] == d["selected"]), None)
    if d["decision"] != "REROUTE":
        c = d["candidates"][0] if d["candidates"] else None
    return c["edges"] if c else []


def primary_cause(oracle_path, learned_path, learned_candidates, learned_decision, labels, oracle_cost, learned_cost):
    """Operational first-blocker taxonomy; not additive causal vehicle-hour effects.

    Missing/derived causes require a repair of those route-cost components to restore the
    oracle ordering. Mixed interactions follow the declared coverage-before-derivation order.
    """
    if oracle_path == learned_path:
        return "G_NO_ACTION_DIFFERENCE"
    if oracle_path not in learned_candidates:
        return "D_CANDIDATE_MISSING"
    if learned_decision.startswith(("REJECTED", "DEFERRED")):
        return "E_OPTIMIZER_REJECTION"
    current = learned_candidates[0]
    for label, cause in (("UNPRICED", "B_COVERAGE_MISSING"), ("DERIVED", "C_DERIVATION_ERROR")):
        def repaired(path):
            return sum(oracle_cost[e] if labels.get(e, "UNPRICED") == label else learned_cost[e] for e in path)
        if repaired(oracle_path) < repaired(current):
            if any(labels.get(e, "UNPRICED") == label for e in set(oracle_path) ^ set(current)):
                return cause
    return "A_FORECAST_ERROR"


def run_seed(source, out, seed, P, cfg, info):
    root = out / f"s{seed}"; root.mkdir(parents=True, exist_ok=True)
    baseline = source / f"s{seed}/baseline"
    snaps = read(baseline / "round_snapshots.json")["snapshots"]
    fc = cl.Forecaster(P, seed)
    routable = {e.getID() for e in info.net.getEdges() if e.allows("passenger")}
    summary_rounds = []
    for snap in snaps:
        k, t = snap["round"], snap["sim_time_s"]
        dest = root / f"round_{k}"; dest.mkdir(exist_ok=True)
        done = dest / "summary.json"
        if done.exists():
            summary_rounds.append(read(done)); continue
        print(f"AUDIT s{seed} round {k}: fresh inference and same-state candidates", flush=True)
        F = fc.predict(t)
        horizons = fc.tables(F, cfg, REPO / P["network"], tuple(P["controller"]["horizons_min"]))
        gwnet = {**horizons[P["horizon_min"]], "time_dependent": {h: v["edge_travel_times"] for h, v in horizons.items()}}
        persistence = fc.table({**F, "pred": np.repeat(F["now"][None, :], 12, axis=0)}, P["horizon_min"], cfg, REPO / P["network"])
        oracle = ec.oracle_table(baseline / "edgedata.xml", REPO / P["network"], cfg, t, t + P["round_s"])
        tables = {"oracle": oracle, "gwnet": gwnet, "persistence": persistence}
        mask = set(gwnet["edges"]) & routable
        labels = {e: r["source"] for e, r in gwnet["edges"].items()}
        trips = [{"id": v, "from": cur, "to": rem[-1], "depart": t, "current_route": rem}
                 for v, (cur, rem) in snap["vehicles"].items() if len(rem) >= 2]
        cands, decisions = {}, {}
        for name, table in tables.items():
            weights = ec.write_weights(table, dest / name / "future_weights.xml", 0, max(P["round_s"], 3600))
            cands[name], _ = ro.candidates_from_sumo(REPO / P["network"], trips, weights, dest / name, cfg, seed)
            decisions[name] = decide_on_candidates(trips, cands[name], table, info, cfg, P, t)
        (dest / "cost_tables.json").write_text(json.dumps({"sources": tables, "edge_labels": labels,
                  "forecast_provenance": {"input_hash": F["input_window_hash"], "forecast_hash": F["raw_prediction_hash"], "checkpoint_sha256": P["checkpoint_sha256"],
                                          "inference_seconds": F["inference_seconds"], "horizons_min": list(horizons)}}, default=str))
        candidate_paths = [p for values in cands.values() for paths in values.values() for p in paths]
        selected_paths = [selected(d) for d in decisions["gwnet"].values()]
        beneficial = [selected(d) for d in decisions["oracle"].values() if d["decision"] == "REROUTE"]
        used = set(e for p in candidate_paths for e in p)
        error = {name: {kind: Errors() for kind in ("DIRECT", "DERIVED", "UNPRICED")} for name in ("gwnet", "persistence")}
        speed_error = {name: {kind: Errors() for kind in ("DIRECT", "DERIVED", "UNPRICED")} for name in error}
        for e in used & oracle["edge_travel_times"].keys():
            for name in error:
                kind = tables[name]["edges"].get(e, {}).get("source", "UNPRICED")
                v = tables[name]["edge_travel_times"].get(e, info.free_tt.get(e, 0))
                truth = oracle["edge_travel_times"][e]
                error[name][kind].add(v - truth)
                if v > 0 and truth > 0:
                    speed_error[name][kind].add(info.length[e] / v - info.length[e] / truth)
        route_errors = {name: Errors() for name in error}; saving_errors = {name: Errors() for name in error}
        ranks = {name: Counter() for name in error}; causes = Counter({c: 0 for c in CAUSES})
        with gzip.open(dest / "vehicle_decisions.jsonl.gz", "wt") as stream:
            for trip in trips:
                vid = trip["id"]; paths = []
                for name in SOURCES:
                    for path in cands[name][vid]:
                        if path not in paths:
                            paths.append(path)
                valued = {name: [ro.route_terms(path, costs(table), info)["forecast_future_tt_s"] for path in paths] for name, table in tables.items()}
                oi = min(range(len(paths)), key=lambda i: valued["oracle"][i])
                cross = []
                for i, path in enumerate(paths):
                    cross.append({"path_hash": path_key(path), "edges": path, "edge_labels": [labels.get(e, "UNPRICED") for e in path],
                                  "cost_s": {name: v[i] for name, v in valued.items()},
                                  "baseline_oracle_observed_edges": sum(e in oracle["edge_travel_times"] for e in path)})
                for name in error:
                    si = min(range(len(paths)), key=lambda i: valued[name][i])
                    ranks[name]["vehicles"] += 1
                    ranks[name]["oracle_top_route_agreement"] += int(paths[si] == paths[oi])
                    for i, j in combinations(range(len(paths)), 2):
                        od, sd = valued["oracle"][i] - valued["oracle"][j], valued[name][i] - valued[name][j]
                        ranks[name]["pairs"] += 1
                        ranks[name]["pair_agreements"] += int((od > 0) - (od < 0) == (sd > 0) - (sd < 0))
                    for i in range(len(paths)):
                        route_errors[name].add(valued[name][i] - valued["oracle"][i])
                    saving_errors[name].add((valued[name][0] - valued[name][si]) - (valued["oracle"][0] - valued["oracle"][oi]))
                    src_reroute = decisions[name][vid]["decision"] == "REROUTE"
                    oracle_reroute = decisions["oracle"][vid]["decision"] == "REROUTE"
                    ranks[name]["false_positive_reroutes"] += int(src_reroute and not oracle_reroute)
                    ranks[name]["false_negative_reroutes"] += int(oracle_reroute and not src_reroute)
                d, o = decisions["gwnet"][vid], decisions["oracle"][vid]
                cause = None
                if o["decision"] == "REROUTE":
                    full_oracle = {e: oracle["edge_travel_times"].get(e, info.free_tt.get(e, 0)) for path in paths for e in path}
                    gw_static = {e: gwnet["edge_travel_times"].get(e, info.free_tt.get(e, 0)) for path in paths for e in path}
                    cause = primary_cause(selected(o), selected(d), cands["gwnet"][vid], d["decision"], labels, full_oracle, gw_static)
                    causes[cause] += 1
                stream.write(json.dumps({"vehicle_id": vid, "round": k, "seed": seed, "state_source": "recorded baseline snapshot",
                    "current_route_edges": trip["current_route"], "candidates": cross,
                    "source_candidate_hashes": {name: [path_key(p) for p in cands[name][vid]] for name in SOURCES},
                    "selected_route": {name: selected(decisions[name][vid]) for name in SOURCES},
                    "admission_result": {name: decisions[name][vid]["decision"] for name in SOURCES},
                    "predicted_saving_s": {name: decisions[name][vid].get("predicted_saving_s") for name in SOURCES},
                    "actual_future_saving_s": None, "actual_saving_status": "counterfactual individual route saving is not observed; oracle costs are baseline edge-window estimates",
                    "primary_failure_cause": cause, "v2x_outcome": "NOT_EXECUTED_IN_SHADOW_REPLAY"}) + "\n")
        oracle_edges = set(oracle["edges"]) & routable
        bottlenecks = {e for e in oracle_edges if oracle["edges"][e]["ratio"] >= 1.3}
        original_round = read(source / f"s{seed}/predictive_v2x/arm_result.json")["rounds"][k]
        row = {"seed": seed, "round": k, "sim_time_s": t,
               "network": {"routable_edges": len(routable), "oracle_priced": len(oracle_edges), "gwnet_direct": sum(labels[e] == "DIRECT" for e in mask),
                           "gwnet_derived": sum(labels[e] == "DERIVED" for e in mask), "unpriced": len(routable - mask), "network_priced_pct": 100 * len(mask) / len(routable),
                           "bottleneck_edges": len(bottlenecks), "bottlenecks_priced": len(bottlenecks & mask), "bottleneck_priced_pct": 100 * len(bottlenecks & mask) / len(bottlenecks) if bottlenecks else None},
               "route_coverage": {"all_candidate_paths": priced_stats(candidate_paths, mask), "gwnet_selected_paths": priced_stats(selected_paths, mask), "oracle_beneficial_paths": priced_stats(beneficial, mask)},
               "edge_time_error_s": {name: {kind: stat.result() for kind, stat in values.items()} for name, values in error.items()},
               "edge_speed_error_mps": {name: {kind: stat.result() for kind, stat in values.items()} for name, values in speed_error.items()},
               "route_error_s": {name: stat.result() for name, stat in route_errors.items()}, "saving_error_s": {name: stat.result() for name, stat in saving_errors.items()},
               "ranking_counts": {name: dict(v) for name, v in ranks.items()}, "opportunity_causes": dict(causes),
               "forecast_hash_matches_reference": F["raw_prediction_hash"] == original_round["raw_prediction_hash"],
               "edge_cost_hash_matches_reference": gwnet["future_cost_hash"] == original_round["future_cost_hash"]}
        done.write_text(json.dumps(row, indent=2)); summary_rounds.append(row)
        print(f"AUDIT DONE s{seed} round {k}: {len(trips)} vehicles", flush=True)
    return summary_rounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/v2x/coverage_diagnostic/scenarioA_fixed_v1/audit")
    parser.add_argument("--seeds", default="201,202,203,204,205")
    args = parser.parse_args()
    source = REPO / "results/v2x/closed_loop" / REFERENCE
    report = read(source / "report.json"); P = report["protocol"]; cfg = ec.load_config()
    assert cfg["_config_hash"] == P["routing_config_hash"]
    assert cl.controller_config()["_hash"] == P["controller_config_hash"]
    out = REPO / args.output; out.mkdir(parents=True, exist_ok=True)
    (out / "PROTOCOL.json").write_text(json.dumps({"scope": "new same-state shadow decision experiment on recorded baseline snapshots, no historical decisions inferred",
        "snapshot_controller_state": "baseline has no prior reroutes; cooldown state empty for all shadow sources",
        "bottleneck_rule": "baseline travel-time/free-flow ratio >= 1.3",
        "cause_rule": "ordered operational diagnosis: same advised action, missing exact oracle candidate, optimizer rejection, missing-edge cost repair, derived-edge cost repair, residual forecast/ranking error",
        "causes_not_vehicle_hour_attribution": True, "actual_individual_counterfactual_saving_observable": False,
        "v2x": "not executed in shadow audit; actual failures reported separately from SUMO arms", "frozen_protocol": P}, indent=2))
    info = ro.NetInfo(REPO / P["network"])
    rows = []
    seeds = [int(s) for s in args.seeds.split(",")]
    assert all(s in report["seeds"] for s in seeds)
    for seed in seeds:
        rows.extend(run_seed(source, out, seed, P, cfg, info))
    (out / ("rounds_" + "_".join(map(str, seeds)) + ".json")).write_text(json.dumps(rows, indent=1))
    print(f"AUDIT COMPLETE {len(rows)} rounds", flush=True)


if __name__ == "__main__":
    main()
