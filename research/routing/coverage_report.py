#!/usr/bin/env python3
"""Assemble coverage diagnostics only when all prescribed runs and rounds are complete."""
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]
from research.routing.coverage_diagnostic import REFERENCE, ARMS, read
from research.routing.coverage_analysis import Errors
from research.routing.coverage_scoring import score_all
from traffictwin.protocols.oracle_gate import paired
from traffictwin.research_status import compute_research_status
from traffictwin.forecasting import ModelRegistry

KEY = "total_vehicle_hours_incl_never_inserted"


def merge_errors(rows):
    n = sum(r["n"] for r in rows)
    return {"n": n, "MAE": sum(r["MAE"] * r["n"] for r in rows if r["n"]) / n if n else None,
            "RMSE": math.sqrt(sum(r["RMSE"] ** 2 * r["n"] for r in rows if r["n"]) / n) if n else None,
            "signed_bias": sum(r["signed_bias"] * r["n"] for r in rows if r["n"]) / n if n else None}


def route_coverage(rows):
    sums = {k: sum(r[k] for r in rows) for k in ("routes", "edge_occurrences", "priced_occurrences", "fully_priced_paths", "partially_priced_paths", "zero_coverage_paths")}
    sums["priced_edge_pct"] = 100 * sums["priced_occurrences"] / sums["edge_occurrences"] if sums["edge_occurrences"] else None
    for key in ("fully_priced_paths", "partially_priced_paths", "zero_coverage_paths"):
        sums[key + "_pct"] = 100 * sums[key] / sums["routes"] if sums["routes"] else None
    return sums


def effect_partition(records):
    per_seed = []
    for seed, arms in records.items():
        o, c, g = (arms[a]["metrics"][KEY] for a in ("oracle_v2x", "oracle_coverage_limited_v2x", "predictive_v2x"))
        gap = g - o
        per_seed.append({"seed": seed, "oracle_gap_vehicle_hours": gap, "coverage_contrast_vehicle_hours": c - o,
                         "forecast_value_contrast_vehicle_hours": g - c,
                         "coverage_pct": 100 * (c - o) / gap if gap else None,
                         "forecast_value_pct": 100 * (g - c) / gap if gap else None})
    gap = sum(r["oracle_gap_vehicle_hours"] for r in per_seed)
    coverage = sum(r["coverage_contrast_vehicle_hours"] for r in per_seed)
    forecasting = sum(r["forecast_value_contrast_vehicle_hours"] for r in per_seed)
    return {"per_seed": per_seed, "oracle_gap_vehicle_hours": gap,
            "coverage_contrast_pct": 100 * coverage / gap if gap else None,
            "forecast_value_contrast_pct": 100 * forecasting / gap if gap else None,
            "candidate_generation_pct": None, "optimizer_admission_pct": None, "v2x_pct": None,
            "interpretation": "telescoping observed contrasts, not independent additive mechanisms: candidate, admission and V2X effects are mediated by each information intervention and cannot be separately assigned vehicle-hour shares from these arms",
            "negative_or_over_100_percent_values_preserved": True}


def actual_channel_outcomes(folder):
    channels = Counter(); application = Counter(); missing_oracle = []
    measured_active, covered_active = 0, 0
    for seed in range(201, 206):
        for arm in ARMS:
            root = folder / f"s{seed}" / arm
            for path in (root / "messages_downlink.jsonl",):
                for line in path.read_text().splitlines():
                    channels[json.loads(line)["status"]] += 1
            for line in (root / "reroute_log.jsonl").read_text().splitlines():
                application[json.loads(line)["outcome"]] += 1
            for path in root.glob("routing_round_*/edge_cost_table.json"):
                table = read(path)
                if arm == "oracle_coverage_limited_v2x":
                    missing_oracle.append(len(table["oracle_unobserved_covered_edges"]))
                    if path.parent.name != "routing_round_11":
                        covered_active += table["priced_edges"]
                        measured_active += table["priced_edges"] - len(table["oracle_unobserved_covered_edges"])
    return {"diagnostic_arms_downlink_outcomes": dict(channels), "diagnostic_arms_application_outcomes": dict(application),
            "oracle_unobserved_covered_edges_per_round": missing_oracle,
            "active_oracle_replacement": {"covered_edge_rounds": covered_active, "observed_edge_rounds": measured_active,
                "observed_pct": 100 * measured_active / covered_active if covered_active else None},
            "scope": "actual diagnostic simulations, separate population from same-state shadow decisions"}


def reference_channel_outcomes(folder):
    result = {}
    for arm in ("oracle_v2x", "predictive_v2x", "persistence_v2x"):
        downlink, application = Counter(), Counter()
        ages = defaultdict(list)
        for seed in range(201, 206):
            root = folder / f"s{seed}" / arm
            for line in (root / "messages_downlink.jsonl").read_text().splitlines():
                downlink[json.loads(line)["status"]] += 1
            for line in (root / "reroute_log.jsonl").read_text().splitlines():
                event = json.loads(line)
                application[event["outcome"]] += 1
                if event.get("created_s") is not None:
                    ages[event["outcome"]].append(event["sim_time_s"] - event["created_s"])
        result[arm] = {"downlink": dict(downlink), "application": dict(application),
                       "applied_pct_of_delivered": 100 * application["APPLIED"] / downlink["DELIVERED"] if downlink["DELIVERED"] else None,
                       "recommendation_age_at_application_attempt_s": {k: {"n": len(v), "median": statistics.median(v), "max": max(v)} for k, v in ages.items()},
                       "timing_scope": "age since planning includes the frozen 5-second recommendation stagger; it is not radio latency"}
    return result


def main():
    folder = REPO / "results/v2x/coverage_diagnostic/scenarioA_fixed_v1"
    ref = read(REPO / "results/v2x/closed_loop" / REFERENCE / "report.json")
    rounds = [read(folder / f"audit/s{s}/round_{k}/summary.json") for s in ref["seeds"] for k in range(12)]
    assert len(rounds) == 60
    evaluated_rounds = [r for r in rounds if r["network"]["oracle_priced"] > 0]
    records = {r["seed"]: {a: r["arms"][a] for a in ("baseline", "reactive", "oracle_v2x", "predictive_v2x", "persistence_v2x", "random_v2x")} for r in ref["per_seed"]}
    for seed in ref["seeds"]:
        for arm in ARMS:
            records[seed][arm] = read(folder / f"s{seed}/{arm}/arm_result.json")
            assert records[seed][arm]["fork"]["state_sha256"] == records[seed]["oracle_v2x"]["fork"]["state_sha256"]
    comparisons = {(a, b) for a in ("oracle_v2x", "oracle_coverage_limited_v2x", "predictive_v2x", "persistence_v2x", "gwnet_direct_v2x") for b in ("reactive", "oracle_v2x", "predictive_v2x", "persistence_v2x") if a != b}
    paired_stats = {f"{a}_vs_{b}": paired(records, a, b, KEY, True) for a, b in sorted(comparisons)}
    network = {}
    for key in rounds[0]["network"]:
        values = [r["network"][key] for r in rounds if r["network"][key] is not None]
        network[key] = {"min": min(values), "max": max(values), "mean": sum(values) / len(values)} if values else None
    coverage = {key: route_coverage([r["route_coverage"][key] for r in evaluated_rounds]) for key in rounds[0]["route_coverage"]}
    matched_rounds = score_all(folder, evaluated_rounds, REPO / ref["protocol"]["network"])
    matched = {}
    for metric in ("matched_edge_time_error_s", "route_cost_error_by_coverage_s"):
        matched[metric] = {}
        for name in ("gwnet", "persistence"):
            groups = set(k for row in matched_rounds for k in row[metric][name])
            matched[metric][name] = {k: merge_errors([row[metric][name][k] for row in matched_rounds if k in row[metric][name]]) for k in sorted(groups)}
    matched["pairwise_ranking_by_coverage"] = {}
    for name in ("gwnet", "persistence"):
        grouped = defaultdict(Counter)
        for row in matched_rounds:
            for group, values in row["pairwise_ranking_by_coverage"][name].items():
                grouped[group].update(values)
        matched["pairwise_ranking_by_coverage"][name] = {group: dict(v) | {"accuracy_pct": 100 * v["agreements"] / v["pairs"] if v["pairs"] else None} for group, v in grouped.items()}
    matched["scope"] = matched_rounds[0]["scope"]
    candidate_counts = Counter()
    for row in matched_rounds:
        candidate_counts.update(row["candidate_set_diagnostics"]["counts"])
    matched["candidate_set_diagnostics"] = {"counts": dict(candidate_counts),
        **{k: merge_errors([r["candidate_set_diagnostics"][k] for r in matched_rounds]) for k in (
            "best_own_vs_best_union_oracle_cost_gap_s", "advised_action_vs_best_own_oracle_cost_regret_s")},
        "scope": matched_rounds[0]["candidate_set_diagnostics"]["scope"]}
    errors = {metric: {name: {kind: merge_errors([r[metric][name][kind] for r in evaluated_rounds]) for kind in ("DIRECT", "DERIVED", "UNPRICED")}
                      for name in ("gwnet", "persistence")} for metric in ("edge_time_error_s", "edge_speed_error_mps")}
    route_errors = {metric: {name: merge_errors([r[metric][name] for r in evaluated_rounds]) for name in ("gwnet", "persistence")} for metric in ("route_error_s", "saving_error_s")}
    rankings = {}
    for name in ("gwnet", "persistence"):
        totals = Counter()
        for r in evaluated_rounds:
            totals.update(r["ranking_counts"][name])
        rankings[name] = dict(totals) | {"oracle_top_route_agreement_pct": 100 * totals["oracle_top_route_agreement"] / totals["vehicles"],
                                       "pairwise_accuracy_pct": 100 * totals["pair_agreements"] / totals["pairs"]}
    causes = Counter()
    for r in evaluated_rounds:
        causes.update(r["opportunity_causes"])
    total = sum(causes.values())
    classification = {c: {"count": n, "pct": 100 * n / total if total else None} for c, n in causes.items()}
    missed_causes = Counter({k: 0 for k in causes})
    for row in matched_rounds:
        missed_causes.update(row["missed_oracle_no_gwnet_reroute_causes"])
    missed_total = sum(missed_causes.values())
    missed_classification = {k: {"count": n, "pct": 100 * n / missed_total if missed_total else None} for k, n in missed_causes.items()}
    partition = effect_partition(records)
    reactive_total = sum(arms["reactive"]["metrics"][KEY] for arms in records.values())
    oracle_total = sum(arms["oracle_v2x"]["metrics"][KEY] for arms in records.values())
    recovery = {a: 100 * (reactive_total - sum(arms[a]["metrics"][KEY] for arms in records.values())) / (reactive_total - oracle_total)
                for a in ("predictive_v2x", "persistence_v2x", "oracle_coverage_limited_v2x", "gwnet_direct_v2x")}
    limitation = paired_stats["oracle_coverage_limited_v2x_vs_oracle_v2x"]
    accuracy = paired_stats["oracle_coverage_limited_v2x_vs_predictive_v2x"]
    coverage_supported = limitation["label"] == "HURT"
    interpretation = {
        "coverage_constraint_supported_on_frozen_seeds": coverage_supported,
        "limited_oracle_vs_gwnet_equivalence_established": False,
        "limited_oracle_vs_gwnet_paired_result": accuracy,
        "headroom_unrecovered_by_limited_oracle_pct_point_estimate": 100 - recovery["oracle_coverage_limited_v2x"],
        "conclusion": "Coverage is the leading measured constraint in these diagnostic interventions." if coverage_supported else "The prescribed diagnostic does not establish coverage as the leading constraint.",
        "qualifications": ["No significant difference is not evidence of equivalence or proof GWNet already uses available information optimally.",
            "Native METR-LA forecast validation does not establish calibrated SUMO edge-cost prediction: DIRECT routing-relevant error can be worse than persistence.",
            "Large real applicability losses remain even with ideal radio transport; these experiments do not separately identify their vehicle-hour effect."],
        "next_intervention_proposal_only": "On development seeds and a separate held-out mapping set, evaluate road-class/direction-aware compatible-detector mapping for the uncovered edges occurring on Oracle-beneficial alternatives. Use a shared fixed candidate pool for the mapping/value diagnostic, report DIRECT and proxy calibration against observed SUMO edge costs, and require validation before routing eligibility. Keep the current checkpoint unchanged. Do not fit or choose the mapping on seeds 201-205.",
        "implementation_status": "PROPOSED_ONLY; no coverage expansion, controller tuning, or new model performed"}
    result = {"source_protocol": read(folder / "PROTOCOL.json"), "same_state_audit_protocol": read(folder / "audit/PROTOCOL.json"),
              "network_coverage": network, "route_relevant_coverage": coverage, "routing_relevant_errors": errors,
              "active_round_network_summary": {"oracle_priced_min": min(r["network"]["oracle_priced"] for r in evaluated_rounds),
                  "oracle_priced_max": max(r["network"]["oracle_priced"] for r in evaluated_rounds),
                  "bottleneck_edge_rounds": sum(r["network"]["bottleneck_edges"] for r in evaluated_rounds),
                  "priced_bottleneck_edge_rounds": sum(r["network"]["bottlenecks_priced"] for r in evaluated_rounds),
                  "bottleneck_priced_pct_pooled": 100 * sum(r["network"]["bottlenecks_priced"] for r in evaluated_rounds) / sum(r["network"]["bottleneck_edges"] for r in evaluated_rounds)},
              "route_cost_and_saving_errors": route_errors, "ranking": rankings, "oracle_advised_opportunity_primary_cause": classification,
              "missed_oracle_no_gwnet_reroute_primary_cause": missed_classification,
              "opportunity_scope": "baseline snapshot shadow recommendations after admission/budget, no delivery simulated; F=0 means not evaluated in this population, not absence of real V2X failures. Ordered first-blocker labels are not exclusive root causes: D can hide simultaneous coverage, ranking and control failures; A=0 does not mean forecasts are correct.",
              "paired_vehicle_hours": paired_stats, "per_seed_raw": {s: {a: {"metrics": x["metrics"], "reroutes_applied": x["reroutes_applied"]} for a, x in arms.items()} for s, arms in records.items()},
              "oracle_gap_partition": partition, "oracle_headroom_recovery_pct_ratio_of_sums": recovery,
              "scientific_interpretation": interpretation,
              "matched_population_scoring": matched, "actual_v2x": actual_channel_outcomes(folder),
              "reference_actual_v2x": reference_channel_outcomes(REPO / "results/v2x/closed_loop" / REFERENCE),
              "rounds": rounds, "gates": compute_research_status()["gates"],
              "fresh_forecast_hash_match_rounds": sum(r["forecast_hash_matches_reference"] for r in rounds),
              "cost_hash_match_rounds": sum(r["edge_cost_hash_matches_reference"] for r in rounds),
              "diagnostic_population": {"logged_rounds": len(rounds), "rounds_with_future_oracle_observations": len(evaluated_rounds),
                  "excluded_from_accuracy_and_opportunities": [{"seed": r["seed"], "round": r["round"], "reason": "no future-window observations at simulation end"} for r in rounds if r not in evaluated_rounds],
                  "route_coverage_aggregation": "rounds with future-window observations; all individual rounds retained",
                  "ranking_target": "frozen Oracle edge-cost policy, including its free-flow fallback on unobserved edges; not actual counterfactual route travel times"},
              "missing_identifiability": ["individual actual future savings on untaken routes are not observed", "separate additive candidate/admission/V2X vehicle-hour shares require additional interventions", "post-hoc diagnostics on existing evaluation seeds are not new independent confirmation", "source-specific DIRECT/DERIVED validity masks differ slightly; matched_population_scoring fixes labels to GWNet and missing source values use explicit free-flow fallback", "coverage-limited Oracle retains GWNet values where the baseline future window has no measurement; it is not perfect ground truth on every covered edge", "shadow replay compares recommendations on baseline states, not causal attribution of missed actions along divergent historical trajectories"]}
    spec = ModelRegistry.metr_la_gwnet()
    checkpoint_sha = hashlib.sha256(Path(spec.checkpoint_path).read_bytes()).hexdigest()
    assert checkpoint_sha.startswith(ref["protocol"]["checkpoint_sha256"])
    provenance = {"checkpoint_sha256_full_at_report": checkpoint_sha, "checkpoint_matches_frozen_prefix": True,
        "reference_report_sha256": hashlib.sha256((REPO / "results/v2x/closed_loop" / REFERENCE / "report.json").read_bytes()).hexdigest(),
        "forecast_hash_matches": result["fresh_forecast_hash_match_rounds"], "cost_hash_matches": result["cost_hash_match_rounds"],
        "analysis_code_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            REPO / "research/routing" / ("coverage_" + name + ".py") for name in ("diagnostic", "analysis", "scoring", "report")]},
        "scope": "full checkpoint hash verified at report assembly; original per-round checkpoint identifiers are frozen hash prefixes"}
    passes = [read(folder / f"audit/s{r['seed']}/round_{r['round']}/cost_tables.json")["forecast_provenance"] for r in rounds]
    runtimes = [p["inference_seconds"] for p in passes]
    provenance["fresh_checkpoint_forward_passes_in_audit"] = len(passes)
    provenance["inference_runtime_s"] = {"min": min(runtimes), "max": max(runtimes), "mean": sum(runtimes) / len(runtimes)}
    provenance["forecast_contract"] = spec.public()
    assert provenance["reference_report_sha256"] == result["source_protocol"]["reference_report_sha256"]
    (folder / "provenance.json").write_text(json.dumps(provenance, indent=2))
    (folder / "report.json").write_text(json.dumps(result, indent=1))
    with (folder / "network_coverage.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=["seed", "round"] + list(rounds[0]["network"]))
        writer.writeheader()
        writer.writerows({"seed": r["seed"], "round": r["round"], **r["network"]} for r in rounds)
    with (folder / "vehicle_hours.csv").open("w") as f:
        writer = csv.writer(f); writer.writerow(["seed"] + list(records[201]))
        for s, arms in records.items():
            writer.writerow([s] + [x["metrics"][KEY] for x in arms.values()])
    lines = ["# Frozen Scenario A: Coverage Diagnostic", "", "All ten new SUMO interventions and all 60 same-state audit rounds completed.", "",
             "The existing frozen FULL ORACLE, GWNet, Persistence, Reactive and Baseline outcomes are explicitly reused, not claimed as new simulations. Variants A and C are the same current DIRECT+DERIVED implementation; B and D are the ten new runs.", "",
             f"Accuracy and opportunity summaries use {len(evaluated_rounds)} rounds with future Oracle observations. The five simulation-end ticks remain logged but are not accuracy evidence.", "",
             "## Network Coverage", "", "| Quantity | Min | Mean | Max |", "|---|---:|---:|---:|"]
    for key, v in network.items():
        if v:
            lines.append(f"| {key} | {v['min']:.3f} | {v['mean']:.3f} | {v['max']:.3f} |")
    lines += ["", f"Oracle-priced edges during active future windows range from {result['active_round_network_summary']['oracle_priced_min']} to {result['active_round_network_summary']['oracle_priced_max']}. Pooled bottleneck coverage is {result['active_round_network_summary']['bottleneck_priced_pct_pooled']:.2f}%. Zero Oracle coverage occurs at the simulation-end tick."]
    lines += ["", "## Route Coverage", "", "| Paths | Priced edge occurrences (%) | Fully priced (%) | Partially priced (%) | Zero coverage (%) |", "|---|---:|---:|---:|---:|"]
    for key, v in coverage.items():
        lines.append(f"| {key} | {v['priced_edge_pct']:.2f} | {v['fully_priced_paths_pct']:.2f} | {v['partially_priced_paths_pct']:.2f} | {v['zero_coverage_paths_pct']:.2f} |")
    lines += ["", "## Traffic Outcomes", "", "| Comparison | Vehicle-hours change (%) | Paired 95% CI | W/L/T |", "|---|---:|---|---|"]
    for pair in ("oracle_v2x_vs_reactive", "oracle_coverage_limited_v2x_vs_reactive", "predictive_v2x_vs_reactive", "persistence_v2x_vs_reactive", "gwnet_direct_v2x_vs_predictive_v2x", "oracle_coverage_limited_v2x_vs_oracle_v2x", "oracle_coverage_limited_v2x_vs_predictive_v2x"):
        v = paired_stats[pair]; lines.append(f"| {pair} | {v['mean_pct']} | {v['ci95']} | {v['wins']}/{v['losses']}/{v['ties']} |")
    lines += ["", "## Gap Contrast", "", f"Coverage contrast: {partition['coverage_contrast_pct']:.2f}% of the aggregate GWNet-to-Oracle gap; forecast-value contrast: {partition['forecast_value_contrast_pct']:.2f}%.",
              "These contrasts include downstream changes in candidates, admission and V2X. They cannot be added to separate mechanism percentages. Negative contributions are retained.", "",
              "## Same-State Ranking", "", "| Source | Oracle top-route agreement (%) | Pairwise accuracy (%) | False positive reroutes | False negative reroutes |", "|---|---:|---:|---:|---:|"]
    for name, v in rankings.items():
        lines.append(f"| {name} | {v['oracle_top_route_agreement_pct']:.2f} | {v['pairwise_accuracy_pct']:.2f} | {v['false_positive_reroutes']} | {v['false_negative_reroutes']} |")
    lines += ["", "Candidate-path identity is strict. Of " + str(candidate_counts["oracle_admitted_opportunities"]) + " Oracle-admitted shadow opportunities, "
              + str(candidate_counts["exact_oracle_path_in_gwnet_set"]) + " exact Oracle paths exist in GWNet's set, but "
              + str(candidate_counts["any_oracle_cheaper_path_in_gwnet_set"]) + " have some Oracle-cheaper candidate in that set. Missing the exact Oracle path does not prove that no useful alternative was generated."]
    lines += ["", "## Matched Routing-Relevant Edge Errors", "", matched["scope"], "",
              "| Source | GWNet coverage class | Edge-round observations | MAE (s) | RMSE (s) | Signed bias (s) |", "|---|---|---:|---:|---:|---:|"]
    for name, groups in matched["matched_edge_time_error_s"].items():
        for kind, v in groups.items():
            lines.append(f"| {name} | {kind} | {v['n']} | {v['MAE']:.3f} | {v['RMSE']:.3f} | {v['signed_bias']:.3f} |")
    lines += ["", "## Missed Oracle Reroutes: Primary Classification", "",
              f"Population: {missed_total} cases where Oracle admits a reroute and GWNet does not. All {total} Oracle-admitted opportunities, including different GWNet reroutes, are separately classified in report.json.", "",
              "| Primary blocker | Count | Percent |", "|---|---:|---:|"]
    for key, v in missed_classification.items():
        lines.append(f"| {key} | {v['count']} | {v['pct']:.2f} |")
    lines += ["", "## Actual Reference V2X Outcomes", "", "| Source | Delivered | Applied | Past fork | Vehicle gone |", "|---|---:|---:|---:|---:|"]
    for arm, v in result["reference_actual_v2x"].items():
        a = v["application"]
        lines.append(f"| {arm} | {v['downlink'].get('DELIVERED', 0)} | {a.get('APPLIED', 0)} | {a.get('INAPPLICABLE_PAST_FORK', 0)} | {a.get('VEHICLE_GONE', 0)} |")
    lines += ["", result["opportunity_scope"], "", "## Computed Gates", "", "| Gate | Status |", "|---|---|"]
    for key in ("FORECAST_VALIDATED", "FUTURE_INFORMATION_VALUE", "PREDICTIVE_CONTROL_VS_REACTIVE", "LEARNED_FORECAST_ADVANTAGE_VS_PERSISTENCE", "DHAKA_DEPLOYMENT_READY"):
        lines.append(f"| {key} | {result['gates'][key]['status']} |")
    lines += ["", "## Identifiability Limits", ""] + ["- " + item for item in result["missing_identifiability"]]
    replacement = result["actual_v2x"]["active_oracle_replacement"]
    lines += ["", f"Oracle observations replace {replacement['observed_edge_rounds']} of {replacement['covered_edge_rounds']} covered edge-round costs ({replacement['observed_pct']:.2f}%) during active future windows. The remainder retains the original learned value. Thus the coverage-limited arm is an observed-Oracle substitution, not a perfect-information bound on all covered edges."]
    lines += ["", "## Scientific Verdict", "", interpretation["conclusion"], "",
              f"The full Oracle reduces vehicle-hours by {-paired_stats['oracle_v2x_vs_reactive']['mean_pct']:.2f}% versus Reactive. Persistence recovers {recovery['persistence_v2x']:.2f}% of aggregate Oracle headroom; GWNet recovers {recovery['predictive_v2x']:.2f}%; coverage-limited Oracle recovers {recovery['oracle_coverage_limited_v2x']:.2f}%.", "",
              f"With the current coverage mask, {interpretation['headroom_unrecovered_by_limited_oracle_pct_point_estimate']:.2f}% of the full Oracle advantage remains unrecovered by this intervention. This is a descriptive point estimate, not a confidence bound or theoretical ceiling.", ""]
    lines += ["- " + item for item in interpretation["qualifications"]]
    lines += ["", "## Next Intervention: Proposal Only", "", interpretation["next_intervention_proposal_only"], "",
              "## Reproduction", "", "```sh", "python research/routing/coverage_diagnostic.py --analyze", "```", "",
              "Completed outputs are reused only after frozen protocol/state checks. The five-seed source reference must be present."]
    lines += ["", "Full edge-error breakdowns, individual decisions, per-round coverage, raw outcomes and computed gates are in report.json and audit/s*/round_*/vehicle_decisions.jsonl.gz.", "",
              "No new forecasting model, mapping expansion or evaluation-seed tuning was performed."]
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    print(folder / "report.json")


if __name__ == "__main__":
    main()
