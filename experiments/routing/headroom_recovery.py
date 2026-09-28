#!/usr/bin/env python3
"""Compute the fixed Scenario-A learned-headroom analysis from closed-loop logs.

This is analysis only: it neither changes the scenario nor reruns SUMO.  It performs a new
checkpoint forward pass at every logged Graph WaveNet routing round and verifies that its output
hash agrees with the frozen closed-loop record.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from traffictwin.protocols.oracle_gate import paired  # noqa: E402
from pipeline.v2x.closed_loop import Forecaster  # noqa: E402
from traffictwin.research_status import compute_research_status  # noqa: E402

KEY = "total_vehicle_hours_incl_never_inserted"
ARMS = ("baseline", "reactive", "persistence_v2x", "predictive_v2x", "oracle_v2x", "random_v2x")
PAIRS = (("predictive_v2x", "reactive"), ("predictive_v2x", "persistence_v2x"), ("persistence_v2x", "reactive"), ("oracle_v2x", "reactive"), ("predictive_v2x", "oracle_v2x"))


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def trip_enrichment(path: Path, duration_s: float) -> dict:
    trips = list(ET.parse(path).getroot().iter("tripinfo"))
    durations = [float(t.get("duration")) for t in trips if t.get("duration") is not None]
    return {
        "median_travel_time_s": round(statistics.median(durations), 3) if durations else None,
        "stops_waiting_count": sum(int(float(t.get("waitingCount", "0"))) for t in trips),
        "throughput_arrivals_per_hour": round(len(trips) * 3600 / duration_s, 3),
    }


def fresh_forward_audit(run: Path, report: dict) -> list[dict]:
    rows = []
    P = report["protocol"]
    for seed in report["seeds"]:
        arm = read(run / f"s{seed}" / "predictive_v2x" / "arm_result.json")
        fc = Forecaster(P, seed)
        for round_record in arm.get("rounds") or []:
            fresh = fc.predict(round_record["sim_time_s"])
            rows.append({
                "seed": seed, "round": round_record["round"], "as_of_index": fresh["as_of"],
                "checkpoint_sha256": P["checkpoint_sha256"], "input_tensor_hash": fresh["input_window_hash"],
                "forecast_hash": fresh["raw_prediction_hash"], "stored_forecast_hash": round_record["raw_prediction_hash"],
                "hash_matches_frozen_run": fresh["raw_prediction_hash"] == round_record["raw_prediction_hash"],
                "edge_cost_hash": round_record["future_cost_hash"], "inference_runtime_s": fresh["inference_seconds"],
                "horizon_min": P["horizon_min"], "direct_priced_edges": round_record.get("direct_edges"),
                "derived_priced_edges": round_record.get("derived_edges"), "priced_edges": round_record.get("priced_edges"),
            })
    return rows


def delivery_and_applicability(run: Path, seeds: list[int]) -> dict:
    out = {"E_v2x_delivery_timing_or_loss": 0, "F_route_no_longer_applicable": 0}
    for seed in seeds:
        arm = run / f"s{seed}" / "predictive_v2x"
        down = arm / "messages_downlink.jsonl"
        if down.exists():
            out["E_v2x_delivery_timing_or_loss"] += sum(1 for line in down.read_text().splitlines() if line and read_json(line).get("status") != "DELIVERED")
        reroutes = arm / "reroute_log.jsonl"
        if reroutes.exists():
            out["F_route_no_longer_applicable"] += sum(1 for line in reroutes.read_text().splitlines() if line and read_json(line).get("outcome") != "APPLIED")
    return out


def read_json(line: str) -> dict:
    return json.loads(line)


def actual_decision_diagnostics(run: Path, seeds: list[int]) -> tuple[dict, dict]:
    """Compare actual logged controller decisions without replaying SUMO or candidates.

    Frozen records omit candidate edge lists, so exact pairwise ranking and A/B attribution are
    deliberately reported as unobservable rather than approximated.
    """
    result, causes = {}, {"A_wrong_forecast_or_route_ranking": 0, "B_unpriced_or_unmapped_edge": 0,
                          "C_candidate_generation_failure": 0, "D_optimizer_or_admission_rejection": 0,
                          "UNRESOLVED_A_OR_B_FROZEN_CANDIDATES_NOT_LOGGED": 0}
    for source, arm in (("persistence", "persistence_v2x"), ("gwnet", "predictive_v2x"), ("oracle", "oracle_v2x")):
        count = agree = fp = fn = 0; saving_errors = []
        for seed in seeds:
            sdir = run / f"s{seed}"; records = {}
            for label, which in (("source", arm), ("oracle", "oracle_v2x")):
                records[label] = {int(path.parent.name.rsplit("_", 1)[-1]): {d["vehicle"]: d for d in read(path).get("decisions") or []}
                                  for path in (sdir / which).glob("routing_round_*/routing_record.json")}
            for rnd in sorted(set(records["source"]) & set(records["oracle"])):
                for vehicle in set(records["source"][rnd]) & set(records["oracle"][rnd]):
                    d, o = records["source"][rnd][vehicle], records["oracle"][rnd][vehicle]; count += 1
                    same = (d["decision"] != "REROUTE" and o["decision"] != "REROUTE") or (d.get("route_signature") == o.get("route_signature") and d.get("route_signature") is not None)
                    agree += int(same); fp += int(d["decision"] == "REROUTE" and o["decision"] != "REROUTE"); fn += int(o["decision"] == "REROUTE" and d["decision"] != "REROUTE")
                    if d.get("predicted_saving_s") is not None and o.get("predicted_saving_s") is not None:
                        saving_errors.append(d["predicted_saving_s"] - o["predicted_saving_s"])
                    if source == "gwnet" and o["decision"] == "REROUTE" and d["decision"] != "REROUTE":
                        if d.get("candidates_real", 0) < 2:
                            causes["C_candidate_generation_failure"] += 1
                        elif d["decision"].startswith(("REJECTED", "DEFERRED")):
                            causes["D_optimizer_or_admission_rejection"] += 1
                        else:
                            causes["UNRESOLVED_A_OR_B_FROZEN_CANDIDATES_NOT_LOGGED"] += 1
        result[source] = {"decisions_compared": count, "top1_route_agreement_with_oracle": round(agree / count, 4) if count else None,
                          "pairwise_ranking_accuracy": "NOT_OBSERVABLE_FROM_FROZEN_LOGS", "false_positive_reroutes": fp,
                          "false_negative_missed_reroutes": fn, "predicted_saving_error_mean_s": round(statistics.fmean(saving_errors), 3) if saving_errors else None,
                          "predicted_saving_abs_error_mean_s": round(statistics.fmean(abs(x) for x in saving_errors), 3) if saving_errors else None}
    result["oracle"]["top1_route_agreement_with_oracle"] = 1.0
    return {"basis": "actual per-arm controller trajectories; after a reroute the arm states diverge, so these are operational agreement diagnostics, not a same-state offline candidate replay",
            "sources": result}, causes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, help="results/v2x/closed_loop/<run>")
    a = p.parse_args(); run = REPO / a.run
    report = read(run / "report.json")
    if tuple(report["arms"]) != ARMS:
        raise SystemExit(f"expected fixed arms {ARMS}, found {report['arms']}")
    if not report.get("fork_state_identical_across_arms"):
        raise SystemExit("identical-state fork check failed")

    per_seed, raw = {}, {}
    for record in report["per_seed"]:
        seed, values = record["seed"], {}
        raw[seed] = {}
        for arm in ARMS:
            metrics = dict(record["arms"][arm]["metrics"])
            metrics.update(trip_enrichment(run / f"s{seed}" / arm / "tripinfo.xml", report["protocol"]["simulation_duration_s"]))
            metrics["stuck_vehicles"] = metrics["unfinished_at_horizon"]
            values[arm] = metrics; raw[seed][arm] = {"metrics": metrics}
        per_seed[seed] = values

    comparisons = {f"{x}_vs_{y}": paired(raw, x, y, KEY, True) for x, y in PAIRS}
    def recovery(source: str) -> dict:
        vals = []
        for seed in report["seeds"]:
            r, s, o = (raw[seed][a]["metrics"][KEY] for a in ("reactive", source, "oracle_v2x"))
            vals.append({"seed": seed, "recovery": (r - s) / (r - o) if r != o else None})
        valid = [x["recovery"] for x in vals if x["recovery"] is not None]
        total = {a: sum(raw[s][a]["metrics"][KEY] for s in report["seeds"]) for a in ("reactive", source, "oracle_v2x")}
        return {"per_seed": vals, "aggregate_ratio_of_sums": (total["reactive"] - total[source]) / (total["reactive"] - total["oracle_v2x"]), "totals": total,
                "mean_per_seed": statistics.fmean(valid) if valid else None}

    audit = fresh_forward_audit(run, report)
    agreement, causes = actual_decision_diagnostics(run, report["seeds"])
    causes.update(delivery_and_applicability(run, report["seeds"]))
    gwn_r, gwn_b, gwn_tel = comparisons["predictive_v2x_vs_reactive"], paired(raw, "predictive_v2x", "baseline", KEY, True), paired(raw, "predictive_v2x", "baseline", "teleports", True)
    predictive_ok = gwn_r["label"] == "HELPED" and gwn_b["label"] == "HELPED" and gwn_tel["label"] != "HURT"
    global_gates = compute_research_status()["gates"]
    gates = {"FORECAST_VALIDATED": global_gates["FORECAST_VALIDATED"], "FUTURE_INFORMATION_VALUE": global_gates["FUTURE_INFORMATION_VALUE"],
             "PREDICTIVE_TRAFFIC_BENEFIT": {"status": "ESTABLISHED" if predictive_ok else "NOT_ESTABLISHED", "rule": "HELPED vs baseline and reactive with teleports not HURT", "scenario_A_only": True,
                                             "vs_reactive": gwn_r, "vs_baseline": gwn_b, "teleports_vs_baseline": gwn_tel},
             "ORACLE_HEADROOM_RECOVERED": {"status": "MEASURED", "gwnet_recovery": recovery("predictive_v2x"), "persistence_recovery": recovery("persistence_v2x")}}
    out = {"run": a.run, "protocol": report["protocol"], "fork_state_identical_across_arms": True, "seeds": report["seeds"], "per_seed_metrics": per_seed,
           "primary_vehicle_hours_comparisons": comparisons, "oracle_headroom_recovery": gates["ORACLE_HEADROOM_RECOVERED"], "fresh_forward_pass_audit": audit,
           "decision_diagnostics": agreement, "missed_oracle_opportunity_contribution_breakdown": causes, "gates": gates}
    target = REPO / "results/v2x/headroom_recovery" / run.name; target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(json.dumps(out, indent=1, default=str))
    gwr, per, ora = (comparisons[k] for k in ("predictive_v2x_vs_reactive", "persistence_v2x_vs_reactive", "oracle_v2x_vs_reactive"))
    lines = ["# Oracle Headroom Recovery", "", f"- Perfect future information vs reactive: {ora['mean_pct']} % (95 % CI {ora['ci95']}).",
             f"- Persistence recovery: {100 * gates['ORACLE_HEADROOM_RECOVERED']['persistence_recovery']['aggregate_ratio_of_sums']:.1f} %.",
             f"- Graph WaveNet recovery: {100 * gates['ORACLE_HEADROOM_RECOVERED']['gwnet_recovery']['aggregate_ratio_of_sums']:.1f} %.",
             f"- Graph WaveNet vs reactive: {gwr['mean_pct']} % (95 % CI {gwr['ci95']}); persistence vs reactive: {per['mean_pct']} % (95 % CI {per['ci95']}).",
             f"- Fresh forward hashes matched frozen routing records: {sum(x['hash_matches_frozen_run'] for x in audit)}/{len(audit)}.", ""]
    (target / "summary.md").write_text("\n".join(lines))
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
