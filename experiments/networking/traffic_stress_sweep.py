#!/usr/bin/env python3
"""STRESS-SCENARIO CALIBRATION — sweep the demand multiplier on DEVELOPMENT seeds, measure how congested the
twin really is (from SUMO's own outputs), and select the operating regime with a rule written here,
before any policy result is looked at.

    python src/pipeline/v2x/stress_sweep.py --city la_c2_hollywood_101_5 --seeds 101,102,103 --scales 1.0,1.5,2.0,2.5,3.0 --profile uniform

Selection rule (frozen before any policy arm is run):
    STABLE      teleports ≤ 1 % of inserted vehicles AND ≥ 85 % of loaded vehicles arrive within the horizon
                AND the loaded network's minimum mean speed stays above 2 m/s (no gridlock) — "loaded" =
                steps with at least a quarter of the peak number of running vehicles
    CONGESTED   at the busiest 300 s interval, ≥ 10 % of major-road edges run at ≥ 70 % of capacity
                (entered vehicles / lanes × 1800 veh/h/lane) AND the loaded network's mean speed is ≤ 70 % of
                the 1.0× value (queues are growing, not just signal stops)
    chosen      the HIGHEST multiplier that is both STABLE and CONGESTED; if none is CONGESTED, the highest
                STABLE one is reported with the gate FAILED (a valid negative: this corridor cannot be
                stressed by demand scaling alone)
    ladder      1, 1.5, 2, 3, 4, 6, 8, 12, 16 × — the sweep stops at the first UNSTABLE level

Revision log (every change made BEFORE any policy arm was simulated on a stress level; the v1 verdicts are
kept in the JSON next to the v2 verdicts):
  v0  "halting ≥ 5 % of running vehicles" as the queue criterion — dropped after the 1.0× baseline showed
      25 % halting from signalised stops alone.
  v1  CONGESTED = ≥ 10 % of major-road EDGES at ≥ 70 % of 1800 veh/h/lane AND loaded speed ≤ 70 % of the
      1.0× value. Outcome on la_c2 (both OD rules): never met at any stable level — the 1800 veh/h/lane
      capacity is unreachable on signalised arterials (green share), and most major-road length carries
      little traffic even at 8×, while SUMO already reports standing jams (statistic.xml: jam teleports
      99 of 149 at 8×). The criterion measured the wrong thing: network-wide lane saturation instead of
      the delay that drivers (and a router) experience.
  v2  CONGESTED = travel-time index TTI = mean travel time / 1.0× mean travel time ≥ 1.30 (the usual
      urban-peak "congested" threshold) AND SUMO reports jam-type teleports > 0 (standing queues of
      ≥ 300 s exist somewhere). STABLE unchanged. After the ladder stops, the bracket between the last
      STABLE and the first UNSTABLE level is bisected twice so the chosen level is not an artefact of the
      ladder's step size. This is the rule the gate uses.

The chosen level is written to src/traffictwin/protocols/controller_config.json under "stress_scenario" and the gate
result to results/v2x/stress/<city>/summary.json. Baseline-only runs: no policy is involved in the choice.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.v2x import closed_loop as cl        # noqa: E402

RULE = {"teleport_rate_max": 0.01, "arrival_share_min": 0.85, "loaded_min_speed_mps": 2.0, "tti_min": 1.30, "jam_teleports_min": 1, "bisection_steps": 2,
        "v1_share_major_ge_0.7_min": 0.10, "v1_loaded_speed_ratio_to_1x_max": 0.70}
LADDER = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]


def evaluate(rep: dict, speed_1x: float | None = None, tt_1x: float | None = None) -> dict:
    rows = []
    for r in rep["per_seed"]:
        m = r["arms"]["baseline"]["metrics"]; c = m["congestion"]; loaded = r["demand"]["vehicles"]
        rows.append({"seed": r["seed"], "vehicles_loaded": loaded, "inserted": m.get("inserted"), "arrived": m.get("arrived"), "teleports": m.get("teleports"),
                     "teleport_rate": (m.get("teleports") or 0) / max(m.get("inserted") or 1, 1), "arrival_share": (m.get("arrived") or 0) / max(loaded, 1),
                     "mean_travel_time_s": m.get("mean_travel_time_all"), "p95_travel_time_s": m.get("p95_travel_time_s"), "total_waiting_s": m.get("total_waiting_s"), "mean_queue_veh": m.get("mean_queue_veh"), "vehicle_hours": m.get("total_vehicle_hours_incl_never_inserted"),
                     "util_p50": c["busiest_interval_utilisation"]["p50"], "util_p90": c["busiest_interval_utilisation"]["p90"], "util_max": c["busiest_interval_utilisation"]["max"], "share_major_ge_0.7": c["busiest_interval_utilisation"]["share_ge_0.7"], "share_major_ge_0.9": c["busiest_interval_utilisation"]["share_ge_0.9"],
                     "mean_occupancy_pct": c["mean_occupancy_pct_major"], "spillback_edges": c["spillback_major_edges_occ_ge_80"], "max_halting": c["max_halting_vehicles"], "max_running": c["max_running_vehicles"], "mean_speed_mps": c["mean_speed_mps"],
                     "loaded_mean_speed_mps": c["loaded_mean_speed_mps"], "loaded_min_speed_mps": c["loaded_min_speed_mps"], "loaded_mean_halting_share": c["loaded_mean_halting_share"], "loaded_max_halting_share": c["loaded_max_halting_share"],
                     "jam_teleports": (c.get("teleport_reasons") or {}).get("jam", 0), "teleport_reasons": c.get("teleport_reasons") or {}})
    mean = lambda k: round(statistics.fmean(x[k] for x in rows if x[k] is not None), 4) if any(x[k] is not None for x in rows) else None
    agg = {k: mean(k) for k in rows[0] if k not in ("seed", "teleport_reasons")}
    stable = agg["teleport_rate"] <= RULE["teleport_rate_max"] and agg["arrival_share"] >= RULE["arrival_share_min"] and (agg["loaded_min_speed_mps"] or 0) >= RULE["loaded_min_speed_mps"]
    ratio = (agg["loaded_mean_speed_mps"] / speed_1x) if (speed_1x and agg["loaded_mean_speed_mps"]) else None
    tti = (agg["mean_travel_time_s"] / tt_1x) if (tt_1x and agg["mean_travel_time_s"]) else None
    agg["loaded_speed_ratio_to_1x"] = round(ratio, 3) if ratio is not None else None
    agg["tti"] = round(tti, 3) if tti is not None else None
    congested_v1 = (agg["share_major_ge_0.7"] or 0) >= RULE["v1_share_major_ge_0.7_min"] and ratio is not None and ratio <= RULE["v1_loaded_speed_ratio_to_1x_max"]
    congested = tti is not None and tti >= RULE["tti_min"] and (agg["jam_teleports"] or 0) >= RULE["jam_teleports_min"]
    return {"per_seed": rows, "mean": agg, "STABLE": stable, "CONGESTED": congested, "CONGESTED_v1": congested_v1}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="la_c2_hollywood_101_5"); p.add_argument("--seeds", default="101,102,103"); p.add_argument("--scales", default=",".join(str(x) for x in LADDER))
    p.add_argument("--profile", default="uniform", choices=sorted(cl.PROFILES_DEMAND)); p.add_argument("--duration-s", dest="duration_s", type=int, default=3600); p.add_argument("--moment", default="prepeak"); p.add_argument("--od-rule", dest="od_rule", default="any", choices=sorted(cl.OD_RULES))
    a = p.parse_args(); seeds = [int(x) for x in a.seeds.split(",")]; scales = [float(x) for x in a.scales.split(",")]
    out = REPO / "results/v2x/stress" / a.city; out.mkdir(parents=True, exist_ok=True)
    points = []; ref = {"speed": None, "tt": None}
    def existing(sc):
        """a finished baseline sweep run for this level (same city/profile/OD rule/seeds): re-evaluated, not re-simulated"""
        tag = "_".join(x for x in ["stress", f"x{sc:g}" if sc != 1.0 else "", a.profile if a.profile != "uniform" else "", a.od_rule if a.od_rule != "any" else ""] if x)
        for rp in (REPO / "results/v2x/closed_loop").glob(f"{a.city}_{a.moment}_ideal_p0_cfg*_{tag}/report.json"):
            rep = json.loads(rp.read_text())
            if sorted(rep.get("seeds", [])) == sorted(seeds) and all("baseline" in r["arms"] for r in rep["per_seed"]) and float(rep["protocol"].get("demand_scale", 1.0)) == sc:
                rep["run_dir"] = str(rp.parent.relative_to(REPO))
                for r in rep["per_seed"]:                                          # congestion metrics recomputed from the run's own SUMO outputs (the metric code may be newer than the run)
                    r["arms"]["baseline"]["metrics"]["congestion"] = cl.congestion_metrics(rp.parent / f"s{r['seed']}" / "baseline", REPO / rep["protocol"]["network"], 0.0, float(rep["protocol"]["simulation_duration_s"]))
                print(f"[stress] {sc}x: re-evaluating finished run {rep['run_dir']}", flush=True)
                return rep
        return None
    def run_level(sc):
        print(f"\n[stress] {a.city} scale {sc}x profile {a.profile} od {a.od_rule} seeds {seeds}", flush=True)
        rep = existing(sc) or cl.run_point(a.city, seeds, "ideal", 0.0, a.moment, ("baseline",), tag="stress", reuse=False, duration_s=a.duration_s, demand_scale=sc, demand_profile=a.profile, od_rule=a.od_rule)
        ev = evaluate(rep, ref["speed"], ref["tt"]); m = ev["mean"]
        if sc == 1.0:
            ref["speed"], ref["tt"] = m["loaded_mean_speed_mps"], m["mean_travel_time_s"]
        pt = {"scale": sc, "run_dir": rep.get("run_dir"), **ev}; points.append(pt); points.sort(key=lambda p: p["scale"])
        print(f"[stress] {sc}x: vehicles {m['vehicles_loaded']:.0f} arrived {m['arrival_share']:.2f} teleports {m['teleport_rate']:.3f} (jam {m['jam_teleports']}) | util p50/p90/max {m['util_p50']}/{m['util_p90']}/{m['util_max']} share≥0.7 {m['share_major_ge_0.7']} occ {m['mean_occupancy_pct']}% spill {m['spillback_edges']} | loaded speed {m['loaded_mean_speed_mps']} (×{m['loaded_speed_ratio_to_1x']} of 1x) min {m['loaded_min_speed_mps']} | tt {m['mean_travel_time_s']:.0f} s TTI {m['tti']} p95 {m['p95_travel_time_s']:.0f} | STABLE {ev['STABLE']} CONGESTED {ev['CONGESTED']} (v1 {ev['CONGESTED_v1']})", flush=True)
        (out / f"sweep_{a.profile}_{a.od_rule}.json").write_text(json.dumps({"city": a.city, "profile": a.profile, "od_rule": a.od_rule, "od_rule_text": cl.OD_RULES[a.od_rule], "seeds": seeds, "rule": RULE, "points": points, "generated_utc": datetime.now(timezone.utc).isoformat()}, indent=1, default=str))
        return ev
    first_unstable = None
    for sc in scales:
        ev = run_level(sc)
        if not ev["STABLE"] and sc > 1.0:
            print(f"[stress] {sc}x is UNSTABLE — ladder stops here", flush=True); first_unstable = sc; break
    if first_unstable is not None:
        lo = max(pt["scale"] for pt in points if pt["STABLE"]); hi = first_unstable
        for _ in range(RULE["bisection_steps"]):
            mid = round((lo + hi) / 2, 2); ev = run_level(mid)
            if ev["STABLE"]:
                lo = mid
            else:
                hi = mid
        print(f"[stress] bisection: highest STABLE level {lo}x, first UNSTABLE {hi}x", flush=True)
        (out / f"sweep_{a.profile}_{a.od_rule}.json").write_text(json.dumps({"city": a.city, "profile": a.profile, "od_rule": a.od_rule, "od_rule_text": cl.OD_RULES[a.od_rule], "seeds": seeds, "rule": RULE, "points": points, "generated_utc": datetime.now(timezone.utc).isoformat()}, indent=1, default=str))
    ok = [pt for pt in points if pt["STABLE"] and pt["CONGESTED"]]
    stable = [pt for pt in points if pt["STABLE"]]
    chosen = max(ok, key=lambda pt: pt["scale"]) if ok else (max(stable, key=lambda pt: pt["scale"]) if stable else None)
    gate = "VALID_TRAFFIC_STRESS_CASE" if ok else "STRESS_GATE_FAILED"
    summary = {"city": a.city, "profile": a.profile, "od_rule": a.od_rule, "od_rule_text": cl.OD_RULES[a.od_rule], "seeds": seeds, "rule": RULE, "chosen_scale": chosen["scale"] if chosen else None, "gate": gate,
               "reason": "highest multiplier that is STABLE and CONGESTED" if ok else "no multiplier is both stable and congested under the rule — demand scaling alone does not stress this corridor without breaking it",
               "points": [{k: v for k, v in pt.items() if k != "per_seed"} for pt in points], "generated_utc": datetime.now(timezone.utc).isoformat()}
    (out / f"summary_{a.profile}_{a.od_rule}.json").write_text(json.dumps(summary, indent=1, default=str))
    L = [f"# Stress-scenario calibration — {a.city} · profile {a.profile} · OD rule {a.od_rule} · development seeds {seeds}", "", cl.OD_RULES[a.od_rule], "", f"Rule: {json.dumps(RULE)}", "", "| scale | vehicles | arrived | teleport rate (jam) | util p50 / p90 / max (major edges, busiest interval) | share ≥ 0.7 | occupancy % | spillback edges | loaded speed m/s (× of 1x) | loaded min speed | halting share | mean tt s | TTI | p95 s | STABLE | CONGESTED (v2) | v1 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pt in points:
        m = pt["mean"]; L.append(f"| {pt['scale']} | {m['vehicles_loaded']:.0f} | {m['arrival_share']:.2f} | {m['teleport_rate']:.3f} ({m['jam_teleports']:.0f}) | {m['util_p50']} / {m['util_p90']} / {m['util_max']} | {m['share_major_ge_0.7']} | {m['mean_occupancy_pct']} | {m['spillback_edges']} | {m['loaded_mean_speed_mps']} ({m['loaded_speed_ratio_to_1x']}) | {m['loaded_min_speed_mps']} | {m['loaded_mean_halting_share']} | {m['mean_travel_time_s']:.0f} | {m['tti']} | {m['p95_travel_time_s']:.0f} | {pt['STABLE']} | {pt['CONGESTED']} | {pt['CONGESTED_v1']} |")
    L += ["", f"**Gate: {gate}** — chosen scale {summary['chosen_scale']} ({summary['reason']}).", ""]
    (out / f"summary_{a.profile}_{a.od_rule}.md").write_text("\n".join(L))
    cfgp = REPO / "src/traffictwin/protocols/controller_config.json"; cfg = json.loads(cfgp.read_text())
    cfg.setdefault("stress_scenario", {})[f"{a.city}:{a.profile}:{a.od_rule}"] = {"chosen_scale": summary["chosen_scale"], "gate": gate, "rule": RULE, "chosen_utc": summary["generated_utc"], "seeds_used": seeds}
    cfgp.write_text(json.dumps(cfg, indent=2))
    print(f"\n[stress] gate {gate}; chosen scale {summary['chosen_scale']} → written to controller_config.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
