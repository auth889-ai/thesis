#!/usr/bin/env python3
"""NETWORK ABLATION — how V2X latency, packet loss and connected-vehicle penetration change what the
predictive closed loop achieves. Every point is a full pipeline/v2x/closed_loop.run_point execution
(the same seeds, demand, caps and forecasts); baseline and reactive arms are reused across points
where they are provably identical, the predictive arm is always re-run.

    python pipeline/v2x/sweep.py --city la_c4_central_wide --seeds 101,102,103 --grid latency
    python pipeline/v2x/sweep.py --grid loss
    python pipeline/v2x/sweep.py --grid penetration
    python pipeline/v2x/sweep.py --grid all

Runs strictly one point at a time (three concurrent SUMO loops push this machine into swap).
Outputs results/v2x/sweep/<city>_<moment>/sweep_<grid>.{json,csv,md}. Nothing here is a number
typed in: every cell is read from a run report.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.v2x import closed_loop as cl        # noqa: E402

GRIDS = {"latency":     [("ideal", 0.3), ("lat100", 0.3), ("lat500", 0.3), ("lat1000", 0.3), ("lat5000", 0.3)],
         "loss":        [("ideal", 0.3), ("loss05", 0.3), ("loss10", 0.3), ("loss20", 0.3), ("degraded", 0.3)],
         "penetration": [("ideal", 0.0), ("ideal", 0.1), ("ideal", 0.3), ("ideal", 0.5), ("ideal", 0.7), ("ideal", 1.0)]}
KEY = "total_vehicle_hours_incl_never_inserted"


def row(rep: dict, profile: str, pen: float) -> dict:
    P = rep["protocol"]; n = rep["network_summary"] or {}; d = (n.get("downlink") or {}); u = (n.get("uplink") or {})
    pb = (rep["paired"].get("predictive_v2x_vs_baseline") or {}); pr_ = (rep["paired"].get("predictive_v2x_vs_reactive") or {}); rb = (rep["paired"].get("reactive_vs_baseline") or {})
    g = lambda st, k: (st or {}).get(k)
    return {"profile": profile, "latency_ms": P["profile_params"]["latency_ms"], "jitter_ms": P["profile_params"]["jitter_ms"], "loss": P["profile_params"]["loss"], "ttl_s": P["profile_params"]["ttl_s"], "penetration": pen,
            "seeds": len(rep["seeds"]), "connected_vehicles": n.get("connected_vehicles_mean"),
            "uplink_tx": u.get("messages_tx"), "uplink_pdr": u.get("packet_delivery_ratio"), "downlink_tx": d.get("messages_tx"), "downlink_rx": d.get("messages_rx"), "downlink_dropped": d.get("messages_dropped"), "downlink_expired": d.get("messages_expired"),
            "downlink_pdr": d.get("packet_delivery_ratio"), "downlink_latency_median_ms": d.get("latency_median_ms"), "downlink_latency_p95_ms": d.get("latency_p95_ms"), "downlink_latency_p99_ms": d.get("latency_p99_ms"),
            "reroutes_applied": n.get("reroutes_applied_total"), "recommendations_inapplicable": n.get("recommendations_inapplicable_total"),
            "vehicle_hours_pred_vs_base_pct": g(pb.get(KEY), "mean_pct"), "vehicle_hours_pred_vs_base_ci": g(pb.get(KEY), "ci95"), "vehicle_hours_pred_vs_base_wlt": f"{g(pb.get(KEY), 'wins')}/{g(pb.get(KEY), 'losses')}/{g(pb.get(KEY), 'ties')}", "vehicle_hours_pred_vs_base_label": g(pb.get(KEY), "label"),
            "p95_pred_vs_base_pct": g(pb.get("p95_travel_time_s"), "mean_pct"), "waiting_pred_vs_base_pct": g(pb.get("total_waiting_s"), "mean_pct"), "queue_pred_vs_base_pct": g(pb.get("mean_queue_veh"), "mean_pct"), "arrived_pred_vs_base_pct": g(pb.get("arrived"), "mean_pct"), "teleports_pred_vs_base_pct": g(pb.get("teleports"), "mean_pct"),
            "vehicle_hours_pred_vs_reactive_pct": g(pr_.get(KEY), "mean_pct"), "vehicle_hours_pred_vs_reactive_label": g(pr_.get(KEY), "label"), "vehicle_hours_reactive_vs_base_pct": g(rb.get(KEY), "mean_pct"),
            "run_dir": rep.get("run_dir")}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="la_c4_central_wide"); p.add_argument("--seeds", default="101,102,103"); p.add_argument("--moment", default="peak", choices=["rule", "peak"])
    p.add_argument("--grid", default="all", choices=sorted(GRIDS) + ["all"])
    a = p.parse_args(); seeds = [int(x) for x in a.seeds.split(",")]
    grids = sorted(GRIDS) if a.grid == "all" else [a.grid]
    out = REPO / "results/v2x/sweep" / f"{a.city}_{a.moment}"; out.mkdir(parents=True, exist_ok=True)
    for grid in grids:
        rows, done = [], set()
        for profile, pen in GRIDS[grid]:
            if (profile, pen) in done:
                continue
            done.add((profile, pen)); t0 = time.time()
            print(f"\n[sweep:{grid}] {profile} penetration={pen} seeds={seeds}", flush=True)
            arms = ("baseline", "reactive", "predictive_v2x") if pen > 0 else ("baseline", "predictive_v2x")
            rep = cl.run_point(a.city, seeds, profile, pen, a.moment, arms)
            r = row(rep, profile, pen); r["wall_s"] = round(time.time() - t0, 1); rows.append(r)
            print(f"[sweep:{grid}] {profile:<9} p={pen:<4} downlink tx/rx/drop {r['downlink_tx']}/{r['downlink_rx']}/{r['downlink_dropped']} PDR {r['downlink_pdr']} lat med {r['downlink_latency_median_ms']} ms · reroutes {r['reroutes_applied']} · "
                  f"veh-h pred vs base {r['vehicle_hours_pred_vs_base_pct']} % {r['vehicle_hours_pred_vs_base_ci']} {r['vehicle_hours_pred_vs_base_label']} · vs reactive {r['vehicle_hours_pred_vs_reactive_pct']} % ({r['wall_s']} s)", flush=True)
            _write(out, grid, rows, a, seeds)                       # partial results survive an interruption
    return 0


def _write(out: Path, grid: str, rows: list[dict], a, seeds: list[int]) -> None:
    (out / f"sweep_{grid}.json").write_text(json.dumps({"city": a.city, "moment": a.moment, "seeds": seeds, "grid": grid, "generated_utc": datetime.now(timezone.utc).isoformat(),
                                                        "communication": "SIMULATED V2X (pipeline/v2x/channel.py)", "demand": "SYNTHETIC_WHAT_IF randomTrips on the real OSM network", "rows": rows}, indent=1, default=str))
    with open(out / f"sweep_{grid}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    L = [f"# V2X ablation — {grid} · {a.city} · {a.moment} · seeds {seeds}", "", "| profile | latency ms | loss | penetration | connected | downlink tx/rx/drop | PDR | lat med / p95 ms | reroutes | veh-h pred vs base % | 95 % CI | W/L/T | label | p95 tt % | waiting % | queue % | arrived % | pred vs reactive % |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['profile']} | {r['latency_ms']} ± {r['jitter_ms']} | {r['loss']} | {r['penetration']} | {r['connected_vehicles'] and round(r['connected_vehicles'])} | {r['downlink_tx']}/{r['downlink_rx']}/{r['downlink_dropped']} | {r['downlink_pdr']} | {r['downlink_latency_median_ms']} / {r['downlink_latency_p95_ms']} | {r['reroutes_applied']} | "
                 f"{r['vehicle_hours_pred_vs_base_pct']} | {r['vehicle_hours_pred_vs_base_ci']} | {r['vehicle_hours_pred_vs_base_wlt']} | **{r['vehicle_hours_pred_vs_base_label']}** | {r['p95_pred_vs_base_pct']} | {r['waiting_pred_vs_base_pct']} | {r['queue_pred_vs_base_pct']} | {r['arrived_pred_vs_base_pct']} | {r['vehicle_hours_pred_vs_reactive_pct']} |")
    L += ["", "Every row is a full closed-loop execution on the same seeds; baseline/reactive arms reused only where identical (same city, moment, seed, network, routing config, penetration). "
              "Development seeds: these curves are diagnostics, not the frozen final result.", ""]
    (out / f"sweep_{grid}.md").write_text("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
