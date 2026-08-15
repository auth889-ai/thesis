#!/usr/bin/env python3
"""Statistical validation of DUE vs DSO at the congested operating regime.

E3b showed a 23-28% DSO improvement at 1800-3000 trips on 3 seeds. Three seeds
can show an effect; they cannot support a publication claim. This script runs
>= 10 independent seeds per arm and reports the full per-seed metric table,
mean/std/95% CI, Welch's t-test and Cohen's d.

Design decisions, stated:
* Assignment (duaIterate) runs ONCE per arm; the converged route file is then
  simulated under N independent seeds. Seeds vary SUMO's stochastic behaviour
  (insertion, car-following), not the assignment itself — this isolates the
  assignment-policy effect, which is the quantity under test.
* Metrics are computed from SUMO's own tripinfo/statistics outputs, never from
  our own accounting.
* queue/spillback are reported as NOT_MEASURED: this harness has no per-step
  lane observation (that instrumentation belongs to the control gate). Absent
  is reported as absent, never as zero.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics as st
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhakaflow.common.city import get_city
from dhakaflow.routing.demand import build_multi_od_demand
from dhakaflow.routing.graph_router import NetworkGraph
from scripts.run_due_dso import find_sumo_home, run_dua, write_trips


def simulate_seed(city, route_file: Path, seed: int, end_s: float,
                  workdir: Path) -> dict:
    """One seeded simulation; every metric parsed from SUMO's own outputs."""
    stats_f = workdir / f"stats_{seed}.xml"
    trip_f = workdir / f"tripinfo_{seed}.xml"
    cmd = ["sumo", "-n", str(city.network_path), "-r", str(route_file),
           "--begin", "0", "--end", str(end_s), "--seed", str(seed),
           "--no-step-log", "true", "--duration-log.statistics", "true",
           "--statistic-output", str(stats_f),
           "--tripinfo-output", str(trip_f),
           "--time-to-teleport", "300", "--collision.action", "warn"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    row = {"seed": seed, "returncode": proc.returncode}

    # --- demand accounting from statistic-output --------------------------
    if stats_f.exists():
        root = ET.parse(stats_f).getroot()
        veh = root.find("vehicles")
        if veh is not None:
            loaded = int(veh.get("loaded", 0))
            inserted = int(veh.get("inserted", 0))
            running = int(veh.get("running", 0))
            waiting = int(veh.get("waiting", 0))
            row.update({
                "requested": loaded,          # trips in the route file
                "loaded": loaded,
                "inserted": inserted,
                "completed": inserted - running,
                "unfinished": running,
                "insertion_backlog": waiting,
            })
        tp = root.find("teleports")
        row["teleports"] = int(tp.get("total", 0)) if tp is not None else 0
        sf = root.find("safety")
        row["collisions"] = int(sf.get("collisions", 0)) if sf is not None else 0

    # --- trip metrics from tripinfo (completed trips) ---------------------
    durations, waits, losses = [], [], []
    if trip_f.exists():
        for t in ET.parse(trip_f).getroot().iter("tripinfo"):
            durations.append(float(t.get("duration", 0)))
            waits.append(float(t.get("waitingTime", 0)))
            losses.append(float(t.get("timeLoss", 0)))
    if durations:
        durations.sort()
        n = len(durations)
        row.update({
            "throughput": n,
            "total_travel_time_s": round(sum(durations), 1),
            "total_delay_s": round(sum(losses), 1),
            "mean_travel_time_s": round(sum(durations) / n, 2),
            "p95_travel_time_s": round(durations[min(int(0.95 * n), n - 1)], 2),
            "mean_delay_s": round(sum(losses) / n, 2),
            "mean_waiting_s": round(sum(waits) / n, 2),
        })
    row["queue_spillback"] = "NOT_MEASURED (no per-step lane observation in this harness)"
    for f in (stats_f, trip_f):
        f.unlink(missing_ok=True)
    return row


def summarize(vals: list[float]) -> dict:
    n = len(vals)
    mean = st.mean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    # 95% CI with t critical value
    try:
        from scipy import stats as sps
        tcrit = float(sps.t.ppf(0.975, n - 1)) if n > 1 else 0.0
    except ImportError:
        tcrit = 2.262 if n == 10 else 1.96   # t(9, .975) fallback
    half = tcrit * sd / math.sqrt(n) if n > 1 else 0.0
    return {"n": n, "mean": round(mean, 2), "std": round(sd, 2),
            "ci95": [round(mean - half, 2), round(mean + half, 2)]}


def compare(a: list[float], b: list[float], label: str) -> dict:
    """Welch's t-test + Cohen's d for DUE (a) vs DSO (b)."""
    out = {"metric": label, "due": summarize(a), "dso": summarize(b)}
    ma, mb = st.mean(a), st.mean(b)
    out["dso_improvement_percent"] = round(100.0 * (ma - mb) / ma, 2) if ma else None
    try:
        from scipy import stats as sps
        t, p = sps.ttest_ind(a, b, equal_var=False)
        out["welch_t"] = round(float(t), 3)
        out["p_value"] = float(p)
    except ImportError:
        out["welch_t"] = out["p_value"] = None
    # Cohen's d with pooled SD
    sa, sb = st.stdev(a), st.stdev(b)
    pooled = math.sqrt((sa ** 2 + sb ** 2) / 2)
    out["cohens_d"] = round((ma - mb) / pooled, 3) if pooled else None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=15)
    ap.add_argument("--veh-per-pair", type=int, default=120)
    ap.add_argument("--iterations", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=list(range(1, 11)))          # 10 independent seeds
    ap.add_argument("--sim-end", type=float, default=10800.0)
    ap.add_argument("--depart-span", type=float, default=600.0)
    ap.add_argument("--out", default="artifacts/due_dso_stats")
    a = ap.parse_args()

    sumo_home = find_sumo_home()
    city = get_city("dhaka_r1")
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    graph = NetworkGraph.from_sumo_net(city.network_path)
    demand = build_multi_od_demand(graph, n_pairs=a.pairs,
                                   vehicles_per_pair=a.veh_per_pair, seed=42)
    contention = demand.contention_report()
    print(json.dumps(contention, indent=1))
    trips = write_trips(out / "trips.xml", demand, a.depart_span)

    arms: dict[str, dict] = {}
    for label, marginal in (("DUE", False), ("DSO", True)):
        rou, cmd, elapsed = run_dua(sumo_home, city.network_path, trips,
                                    out / label, a.iterations, marginal, a.sim_end)
        if rou is None:
            print(f"{label}: ASSIGNMENT FAILED"); return 1
        rows = [simulate_seed(city, rou, s, a.sim_end, out) for s in a.seeds]
        arms[label] = {"command": cmd, "assignment_seconds": round(elapsed, 1),
                       "per_seed": rows}
        print(f"{label}: {len(rows)} seeds done")

    def col(arm, key):
        return [r[key] for r in arms[arm]["per_seed"] if key in r]

    comparisons = [compare(col("DUE", k), col("DSO", k), k) for k in (
        "total_delay_s", "mean_delay_s", "total_travel_time_s",
        "mean_travel_time_s", "p95_travel_time_s", "mean_waiting_s",
        "throughput")]

    integrity = {
        arm: {
            "all_returncode_zero": all(r["returncode"] == 0 for r in v["per_seed"]),
            "total_collisions": sum(r.get("collisions", 0) for r in v["per_seed"]),
            "total_teleports": sum(r.get("teleports", 0) for r in v["per_seed"]),
            "all_demand_inserted": all(r.get("insertion_backlog", 1) == 0
                                       for r in v["per_seed"]),
            "all_demand_completed": all(r.get("unfinished", 1) == 0
                                        for r in v["per_seed"]),
        } for arm, v in arms.items()
    }

    payload = {
        "stage": "DUE_DSO_STATISTICAL_VALIDATION",
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "design_note": ("Assignment converged once per arm; N independent "
                        "simulation seeds per arm isolate the assignment-policy "
                        "effect. Demand is structured-synthetic (contention-"
                        "verified), not calibrated Dhaka demand."),
        "config": {"pairs": a.pairs, "veh_per_pair": a.veh_per_pair,
                   "total_trips": demand.total_vehicles,
                   "iterations": a.iterations, "seeds": a.seeds,
                   "sim_end_s": a.sim_end},
        "contention": contention,
        "arms": arms,
        "integrity": integrity,
        "comparisons": comparisons,
    }
    (out / "result.json").write_text(json.dumps(payload, indent=2))
    print("\n=== HEADLINE ===")
    for c in comparisons[:3]:
        print(f"{c['metric']:22} DUE {c['due']['mean']:>12,.1f}  "
              f"DSO {c['dso']['mean']:>12,.1f}  "
              f"impr {c['dso_improvement_percent']}%  p={c['p_value']}  "
              f"d={c['cohens_d']}")
    print("artifact:", out / "result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
