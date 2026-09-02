#!/usr/bin/env python3
"""R4/R5: official SUMO Dynamic User Equilibrium vs Dynamic System Optimal.

Both arms are produced by SUMO's OWN `duaIterate.py`, differing by exactly one
documented flag:

    R4 DUE  =  duaIterate.py ...
    R5 DSO  =  duaIterate.py ... --marginal-cost

`--marginal-cost` is SUMO's documented system-optimal mode ("use marginal cost
to perform system optimal traffic assignment"). Using the official tool for both
arms means the DUE/DSO comparison cannot be an artefact of two different
home-made implementations — which is the whole point of the routing ladder.

Neither arm is graded by its own internal cost estimate: both produce route
files, and those route files are then simulated under identical seeds and the
network-wide outcome is measured.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.core.common.city import get_city
from pipeline.core.digital_twin.sumo_runner import SumoTwin
from pipeline.core.routing.demand import build_multi_od_demand
from pipeline.core.routing.graph_router import NetworkGraph


def find_sumo_home() -> Path:
    if os.environ.get("SUMO_HOME"):
        return Path(os.environ["SUMO_HOME"])
    import sumolib
    for parent in Path(sumolib.__file__).resolve().parents:
        cand = parent / "sumo"
        if (cand / "tools" / "assign" / "duaIterate.py").exists():
            return cand
    raise RuntimeError("SUMO_HOME not found; set it explicitly")


def write_trips(path: Path, demand, depart_span_s: float) -> Path:
    """Trip definitions (origin/destination only) — duaIterate chooses the routes."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>"]
    trips = []
    for p in demand.pairs:
        for i in range(p.n_vehicles):
            t = depart_span_s * i / max(p.n_vehicles, 1)
            trips.append((t, f"{p.od_id}_{i}", p.origin, p.destination))
    trips.sort(key=lambda x: x[0])
    for t, vid, o, d in trips:
        lines.append(f'    <trip id="{vid}" depart="{t:.2f}" from="{o}" to="{d}"/>')
    lines.append("</routes>")
    path.write_text("\n".join(lines))
    return path


def run_dua(sumo_home: Path, net: Path, trips: Path, workdir: Path,
            iterations: int, marginal_cost: bool, end_s: float,
            timeout_s: int = 3600) -> tuple[Path | None, str, float]:
    """Run official duaIterate.py; return (final route file, command, seconds)."""
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(sumo_home / "tools" / "assign" / "duaIterate.py"),
        "-n", str(net),
        "-t", str(trips),
        "-l", str(iterations),
        "--nointernal-link",
        # SUMO warns that --marginal-cost works best with --logit. We apply
        # --logit to BOTH arms so the ONLY difference between DUE and DSO stays
        # the single --marginal-cost flag; otherwise the comparison would
        # confound route-choice model with assignment objective.
        "--logit",
        "duarouter--routing-threads", "4",
        "sumo--end", str(end_s),
    ]
    if marginal_cost:
        cmd.insert(cmd.index("-l"), "--marginal-cost")

    env = dict(os.environ, SUMO_HOME=str(sumo_home))
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                          env=env, timeout=timeout_s)
    elapsed = time.time() - t0
    printable = " ".join(cmd)

    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        print(f"  duaIterate FAILED (rc={proc.returncode}):\n{tail}")
        return None, printable, elapsed

    # duaIterate writes <iteration>/ dirs; the last one holds the converged routes.
    # duaIterate writes gzipped route files (trips_<NNN>.rou.xml.gz) and a
    # .rou.alt.xml.gz of alternatives; we want the chosen routes, not the
    # alternative set. SUMO reads .gz directly.
    last = iterations - 1
    for pattern in (f"{last:03d}/*.rou.xml.gz", f"{last:03d}/*.rou.xml",
                    f"{last}/*.rou.xml.gz", f"{last}/*.rou.xml"):
        found = [f for f in sorted(workdir.glob(pattern)) if ".alt." not in f.name]
        if found:
            return found[-1], printable, elapsed
    return None, printable, elapsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="dhaka_r1")
    ap.add_argument("--pairs", type=int, default=20)
    ap.add_argument("--veh-per-pair", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--sim-end", type=float, default=7200.0)
    ap.add_argument("--depart-span", type=float, default=600.0)
    ap.add_argument("--out", default="artifacts/p0_due_dso")
    a = ap.parse_args()

    sumo_home = find_sumo_home()
    city = get_city(a.city)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    graph = NetworkGraph.from_sumo_net(city.network_path)
    demand = build_multi_od_demand(graph, n_pairs=a.pairs,
                                   vehicles_per_pair=a.veh_per_pair, seed=42)
    contention = demand.contention_report()
    print(json.dumps(contention, indent=1))
    if not contention["testable"]:
        print("ABORT: demand has no contended edges")
        return 1

    trips = write_trips(out / "trips.xml", demand, a.depart_span)
    twin = SumoTwin(city)
    results: dict = {}

    for label, marginal in (("R4_DUE", False), ("R5_DSO_marginal_cost", True)):
        print(f"\n=== {label} ===")
        rou, cmd, elapsed = run_dua(sumo_home, city.network_path, trips,
                                    out / label, a.iterations, marginal, a.sim_end)
        entry = {"command": cmd, "assignment_seconds": round(elapsed, 1),
                 "route_file": str(rou) if rou else None,
                 "official_tool": "SUMO duaIterate.py",
                 "marginal_cost_flag": marginal}
        if rou is None:
            entry["status"] = "ASSIGNMENT_FAILED"
            results[label] = entry
            continue

        per_seed = []
        for s in a.seeds:
            run = twin.run(rou, end_s=a.sim_end, seed=s)
            m = run.metrics
            per_seed.append({
                "seed": s, "comparable": run.comparable,
                "avg_time_loss_s": m.avg_time_loss_s,
                "avg_travel_time_s": m.avg_travel_time_s,
                "p95_travel_time_s": m.p95_travel_time_s,
                "avg_waiting_time_s": m.avg_waiting_time_s,
                "throughput_veh": m.throughput_veh,
                "collisions": m.collisions, "teleports": m.teleports,
                "loaded": run.demand.loaded, "inserted": run.demand.inserted,
                "demand_complete": run.demand.is_complete,
            })
        vals = [r["avg_time_loss_s"] for r in per_seed if r["avg_time_loss_s"] is not None]
        entry.update({
            "status": "OK",
            "mean_time_loss_s": statistics.mean(vals) if vals else None,
            "stdev_time_loss_s": statistics.stdev(vals) if len(vals) > 1 else None,
            "all_comparable": all(r["comparable"] for r in per_seed),
            "per_seed": per_seed,
        })
        results[label] = entry
        print(f"  mean time loss = {entry['mean_time_loss_s']}")

    due = results.get("R4_DUE", {}).get("mean_time_loss_s")
    dso = results.get("R5_DSO_marginal_cost", {}).get("mean_time_loss_s")
    verdict = None
    if due and dso:
        verdict = {
            "due_time_loss_s": round(due, 2),
            "dso_time_loss_s": round(dso, 2),
            "dso_improvement_percent": round(100.0 * (due - dso) / due, 2),
            "dso_better": dso < due,
            "interpretation": (
                "DSO assigns on marginal cost, so it should trade a small "
                "penalty for some drivers against lower TOTAL network delay. "
                "A negative improvement means the effect did not materialise at "
                "this demand level and must be reported as such."),
        }

    payload = {
        "stage": "R4_R5_OFFICIAL_SUMO_ASSIGNMENT",
        "city": city.city_id,
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "sumo_home": str(sumo_home),
        "iterations": a.iterations,
        "seeds": a.seeds,
        "contention": contention,
        "results": results,
        "verdict": verdict,
    }
    (out / "result.json").write_text(json.dumps(payload, indent=2))
    print("\n" + json.dumps(verdict or {"verdict": "unavailable"}, indent=2))
    print("artifact:", out / "result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
