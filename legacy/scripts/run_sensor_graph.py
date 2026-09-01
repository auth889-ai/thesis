#!/usr/bin/env python3
"""P2 — generate the simulated sensor-graph dataset on the frozen R1 network.

    python scripts/run_sensor_graph.py                    # SMOKE: 2 sim-hours,
                                                          # 1 seed, local, ~min
    python scripts/run_sensor_graph.py --mode full        # FULL: 24 h × seeds,
                                                          # run on Colab, → Drive

Smoke exists because of the standing rule: smoke test before big runs. The
full run belongs on Colab (notebooks/P2_sensor_graph_colab.ipynb) and writes
to Drive. Output is labelled DHAKA_SIMULATED_SENSOR_GRAPH throughout — it is
simulation on the real frozen topology, never a real measurement.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np

from dhakaflow.common.city import get_city
from dhakaflow.digital_twin.sumo_runner import SumoTwin
from dhakaflow.routing.demand import (AssignmentPolicy, assign_routes,
                                      build_multi_od_demand)
from dhakaflow.routing.graph_router import NetworkGraph
from research.twin.sensor_graph import (DAILY_PROFILE, SENSOR_PERIOD_S,
                                        gaussian_kernel_adjacency,
                                        node_list_sha256, parse_edgedata,
                                        road_distances, save_dataset,
                                        select_sensor_edges,
                                        write_sensor_additional)


def write_profiled_routes(path: Path, routes: dict, counts: dict,
                          hours: list[int], scale: float) -> tuple[Path, int]:
    """Route file with DAILY_PROFILE-scaled hourly departures (non-stationary)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>"]
    for rid, edges in routes.items():
        lines.append(f'    <route id="{rid}" edges="{" ".join(edges)}"/>')
    vehicles = []
    for h_idx, hour in enumerate(hours):
        factor = DAILY_PROFILE[hour % 24] * scale
        for rid, base in counts.items():
            n = int(round(base * factor))
            for i in range(n):
                t = h_idx * 3600.0 + 3600.0 * i / max(n, 1)
                vehicles.append((t, f"{rid}_h{hour}_{i}", rid))
    vehicles.sort(key=lambda v: v[0])
    for t, vid, rid in vehicles:
        lines.append(f'    <vehicle id="{vid}" route="{rid}" depart="{t:.2f}"/>')
    lines.append("</routes>")
    path.write_text("\n".join(lines))
    return path, len(vehicles)


def repair_routes(net_path: Path, rou: Path, out: Path) -> Path:
    """Repair graph-level paths into SUMO-drivable routes with duarouter.

    NetworkGraph edges can be adjacent without a passenger lane connection, so
    a small fraction of assigned paths is undrivable. duarouter (SUMO's own
    tool) rewrites those while keeping vehicles and departure times; dropping
    them instead would silently change the demand.
    """
    import subprocess
    r = subprocess.run(
        ["duarouter", "-n", str(net_path), "--route-files", str(rou),
         "-o", str(out), "--repair", "true", "--repair.from", "true",
         "--repair.to", "true", "--no-step-log", "true"],
        capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"duarouter repair failed:\n{r.stderr[-2000:]}")
    n_warn = r.stderr.count("Warning")
    if n_warn:
        print(f"[P2] duarouter repaired/warned on {n_warn} route(s)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--city", default="dhaka_r1")
    ap.add_argument("--n-sensors", type=int, default=250)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--hours", type=int, nargs="+", default=None,
                    help="hours of day to simulate (full default: 0..23)")
    ap.add_argument("--demand-scale", type=float, default=None)
    ap.add_argument("--od-pairs", type=int, default=None,
                    help="OD relations (smoke default 40; full default 150 so "
                         "demand paths reach most of the 250 sensors)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    smoke = a.mode == "smoke"
    seeds = a.seeds or ([42] if smoke else [42, 43, 44])
    hours = a.hours or ([7, 8] if smoke else list(range(24)))
    scale = a.demand_scale if a.demand_scale is not None else (0.3 if smoke else 1.0)
    out = a.out or (REPO / "artifacts" /
                    ("p2_sensor_graph_smoke" if smoke else "p2_sensor_graph"))

    city = get_city(a.city)
    print(f"[P2] mode={a.mode} city={city.city_id} sensors={a.n_sensors} "
          f"seeds={seeds} hours={hours} scale={scale}")

    print("[P2] parsing network + selecting sensors (deterministic)…")
    nodes = select_sensor_edges(city.network_path, n_target=a.n_sensors)
    print(f"[P2] {len(nodes)} sensors, node_list_sha256={node_list_sha256(nodes)[:16]}…")

    graph = NetworkGraph.from_sumo_net(city.network_path)
    n_pairs = a.od_pairs or (40 if smoke else 150)
    demand = build_multi_od_demand(graph, n_pairs=n_pairs,
                                   vehicles_per_pair=60, seed=42)
    report = demand.contention_report()
    print(f"[P2] demand: {report['n_od_pairs']} OD pairs, "
          f"{report['n_contended_edges']} contended edges, "
          f"testable={report['testable']}")
    routes, counts = assign_routes(demand, AssignmentPolicy.USER_OPTIMAL)

    twin = SumoTwin(city)                     # verifies the frozen checksum
    end_s = len(hours) * 3600.0
    all_data, all_mask, per_seed = [], [], []

    for seed in seeds:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            edgedata = tmpdir / f"edgedata_seed{seed}.xml"
            add = write_sensor_additional(nodes, tmpdir / "sensors.add.xml",
                                          edgedata)
            raw_rou, n_veh = write_profiled_routes(
                tmpdir / f"routes_seed{seed}.rou.xml", routes, counts,
                hours, scale)
            rou = repair_routes(city.network_path, raw_rou,
                                tmpdir / f"routes_seed{seed}.repaired.rou.xml")
            print(f"[P2] seed {seed}: {n_veh} vehicles over {end_s:.0f}s — running SUMO…")
            t0 = time.time()
            result = twin.run(rou, end_s=end_s, seed=seed,
                              extra_args=["-a", str(add)])
            wall = time.time() - t0
            if result.sumo_returncode != 0:
                print(result.stderr_excerpt)
                raise RuntimeError(f"SUMO failed for seed {seed}")
            data, mask = parse_edgedata(edgedata, [n.edge_id for n in nodes])
            all_data.append(data)
            all_mask.append(mask)
            per_seed.append({
                "seed": seed, "timesteps": int(data.shape[0]),
                "vehicles": n_veh, "wall_s": round(wall, 1),
                "insertion_rate": result.demand.insertion_rate,
                "teleports": result.metrics.teleports,
                "coverage_pct": round(100.0 * float(mask.mean()), 1),
            })
            print(f"[P2] seed {seed}: {data.shape[0]} bins, "
                  f"coverage {per_seed[-1]['coverage_pct']}%, "
                  f"insertion {result.demand.insertion_rate:.2f}, "
                  f"{wall:.0f}s wall")

    data = np.concatenate(all_data)           # seeds = consecutive sim days
    mask = np.concatenate(all_mask)

    print("[P2] computing DCRNN-recipe adjacency…")
    dist = road_distances(graph, [n.edge_id for n in nodes])
    adj = gaussian_kernel_adjacency(dist)
    finite_pct = 100.0 * np.isfinite(dist).mean()
    nnz_pct = 100.0 * (adj > 0).mean()

    manifest = save_dataset(
        out, data, mask, adj, dist, nodes,
        network_sha256=city.network_sha256, seeds=seeds,
        config={"mode": a.mode, "hours": hours, "demand_scale": scale,
                "od_pairs": report["n_od_pairs"],
                "demand_provenance": "SYNTHETIC_STRUCTURED_DEMAND (pre-calibration)",
                "seed_boundaries_timesteps": [d.shape[0] for d in all_data],
                "per_seed": per_seed})

    print(f"\n[P2] dataset: T={data.shape[0]} × N={data.shape[1]} × C={data.shape[2]}")
    print(f"[P2] mask coverage {100.0 * float(mask.mean()):.1f}% | "
          f"reachable pairs {finite_pct:.1f}% | adjacency nnz {nnz_pct:.1f}%")
    print(f"[P2] manifest: {manifest}")
    print(f"[P2] evidence domain: DHAKA_SIMULATED_SENSOR_GRAPH (never 'real')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
