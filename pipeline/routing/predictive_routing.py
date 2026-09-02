#!/usr/bin/env python3
"""One harness, every routing arm, on the real Dhaka R1 network.

    python pipeline/routing/predictive_routing.py --arm static     --seed 11 --horizon 900
    python pipeline/routing/predictive_routing.py --arm reactive   --seed 11 --horizon 900 --compliance 0.3
    python pipeline/routing/predictive_routing.py --arm predictive --seed 11 --horizon 900 --compliance 0.3 \
        --weights results/routing/static_s11_h900/edgedata.xml      # oracle forecast = truth from the static run

Arms (identical network, demand, seed and horizon; only the routing rule differs):

  static      every vehicle drives its pre-computed shortest route (no rerouting)  -> baseline B1
  reactive    equipped vehicles reroute every --period s on CURRENT edge travel     -> baseline B2
              times: traci.vehicle.rerouteTraveltime(v, currentTravelTimes=True)
  predictive  a time-dependent travel-time table (the FORECAST, SUMO meanData XML)   -> arm P
              is loaded with traci.edge.adaptTraveltime(edge, tt, begin, end); equipped
              vehicles reroute with rerouteTraveltime(v, currentTravelTimes=False), so
              SUMO's time-dependent Dijkstra costs each edge at its predicted arrival time.
  due / dso   offline duaIterate.py (see pipeline/routing/run_due_dso.py; --marginal-cost = DSO)  -> B3 / B4

Outputs (one directory per run): tripinfo.xml, statistic.xml, edgedata.xml (5-min mean
travel time per edge = the oracle weight table for the next predictive run) and
metrics.json (mean/p95 travel time, waiting, time loss, depart delay, throughput, teleports).

Equipped vehicles are chosen deterministically from the vehicle id (md5), so the same
--compliance gives the same equipped set in every arm and every seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_NET = REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"
if not DEFAULT_NET.exists() and DEFAULT_NET.with_suffix(".xml.gz").exists():
    # the repo tracks a 2 MB .gz of the 16 MB network so a fresh clone can run
    import gzip as _gz, shutil as _sh
    with _gz.open(DEFAULT_NET.with_suffix(".xml.gz"), "rb") as _fi, open(DEFAULT_NET, "wb") as _fo:
        _sh.copyfileobj(_fi, _fo)
DEFAULT_ROUTES = REPO / "artifacts/gates/routes_repeat_1h.rou.xml.gz"
DEFAULT_SCALE = 0.584          # calibrated demand scale recorded in artifacts/gates/TWIN_SYNC_PASS.json


def equipped(vid: str, compliance: float) -> bool:
    h = int(hashlib.md5(vid.encode()).hexdigest()[:8], 16)
    return (h % 10_000) < compliance * 10_000


def base_cmd(a, out: Path) -> list[str]:
    add = out / "additional.xml"
    add.write_text('<additional>\n  <edgeData id="ed" file="edgedata.xml" freq="%d" excludeEmpty="true"/>\n</additional>\n'
                   % a.edgedata_period)
    cmd = [a.sumo_binary,
           "--net-file", str(a.net),
           "--route-files", str(a.routes),
           "--additional-files", str(add),
           "--seed", str(a.seed),
           "--scale", str(a.scale),
           "--end", str(a.horizon),
           "--tripinfo-output", str(out / "tripinfo.xml"),
           "--tripinfo-output.write-unfinished",
           "--statistic-output", str(out / "statistic.xml"),
           "--no-step-log", "--no-warnings", "--ignore-route-errors",
           "--time-to-teleport", str(a.time_to_teleport),
           # global travel-time smoothing used by rerouteTraveltime(currentTravelTime=True)
           "--device.rerouting.probability", "0",
           "--device.rerouting.adaptation-interval", "10",
           "--device.rerouting.adaptation-weight", "0.5"]
    # Extra SUMO options shared by EVERY arm/driver (run_arms, incident, predeparture) without CLI plumbing,
    # e.g. DHAKAFLOW_SUMO_EXTRA="--ignore-junction-blocker 60" (gridlock remedy, see results/routing/gridlock_check.md)
    extra = os.environ.get("DHAKAFLOW_SUMO_EXTRA", "").split()
    return cmd + extra


def load_weights(path: Path) -> list[tuple[float, float, str, float]]:
    """SUMO meanData XML -> [(begin, end, edge, traveltime)]."""
    rows = []
    for iv in ET.parse(path).getroot().iter("interval"):
        b, e = float(iv.get("begin")), float(iv.get("end"))
        for ed in iv.iter("edge"):
            tt = ed.get("traveltime")
            if tt is not None:
                rows.append((b, e, ed.get("id"), float(tt)))
    return rows


def run_static(a, out: Path) -> dict:
    subprocess.run(base_cmd(a, out), check=True)
    return {"rerouted_calls": 0, "equipped": 0}


def free_port() -> int:
    """Reserve and release a local port for TraCI startup.

    Some SUMO/TraCI installs fail to auto-pick a port under Python 3.13 and pass
    None through to socket.connect. Supplying the port explicitly keeps the
    harness deterministic enough for local and CI smoke runs.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def run_traci(a, out: Path) -> dict:
    import traci
    cmd = base_cmd(a, out)
    traci.start(cmd, port=free_port(), label=f"{a.arm}-{a.seed}")
    n_calls, eq_seen = 0, set()
    try:
        if a.arm == "predictive":
            rows = load_weights(Path(a.weights))
            for b, e, edge, tt in rows:
                try:
                    traci.edge.adaptTraveltime(edge, tt, b, e)
                except traci.TraCIException:
                    pass
            print(f"[predictive] loaded {len(rows)} (edge, interval) forecast entries from {a.weights}")
        current = a.arm == "reactive"
        t = 0
        while t < a.horizon:
            traci.simulationStep()
            t = int(traci.simulation.getTime())
            if traci.simulation.getMinExpectedNumber() == 0:
                break
            for vid in traci.vehicle.getIDList():
                if not equipped(vid, a.compliance):
                    continue
                eq_seen.add(vid)
                # stagger: each equipped vehicle reroutes once per period at its own offset
                if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % a.period == 0:
                    try:
                        traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=current)
                        n_calls += 1
                    except traci.TraCIException:
                        pass
    finally:
        traci.close()
    return {"rerouted_calls": n_calls, "equipped": len(eq_seen)}


def parse_metrics(out: Path, horizon: float | None = None) -> dict:
    """tripinfo + statistic -> metrics.  The commensurable objective across arms is
    total_vehicle_hours = [sum(duration of arrived) + sum(horizon - depart of unfinished)] / 3600,
    which charges every INSERTED vehicle for its time in the network up to the horizon, so an
    arm cannot look good by finishing fewer (or only the short) trips.  mean_travel_time_all is
    the same numerator divided by (arrived + unfinished).  Vehicles never inserted before the
    horizon are not in tripinfo and are reported separately (waiting_to_insert_at_end).
    `horizon` defaults to what SUMO wrote for unfinished vehicles (duration = end - depart)."""
    durs, waits, losses, dd, unfinished, rerouted, unfinished_s = [], [], [], [], 0, 0, 0.0
    for ti in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
        if float(ti.get("arrival", -1)) < 0:
            unfinished += 1
            unfinished_s += (horizon - float(ti.get("depart"))) if horizon is not None else float(ti.get("duration"))
            continue
        durs.append(float(ti.get("duration")))
        waits.append(float(ti.get("waitingTime")))
        losses.append(float(ti.get("timeLoss")))
        dd.append(float(ti.get("departDelay")))
        rerouted += int(int(ti.get("rerouteNo", 0)) > 0)
    st = ET.parse(out / "statistic.xml").getroot()
    tele = st.find("teleports")
    veh = st.find("vehicles")
    q = lambda xs, p: (sorted(xs)[min(len(xs) - 1, int(p * len(xs)))] if xs else None)
    total_s = sum(durs) + unfinished_s
    return {
        "arrived": len(durs),
        "unfinished_at_horizon": unfinished,
        "unfinished": unfinished,
        "total_vehicle_hours": total_s / 3600.0,
        "mean_travel_time_all": total_s / (len(durs) + unfinished) if (durs or unfinished) else None,
        "mean_travel_time_s": statistics.fmean(durs) if durs else None,
        "p95_travel_time_s": q(durs, 0.95),
        "mean_waiting_s": statistics.fmean(waits) if waits else None,
        "total_waiting_s": sum(waits),
        "mean_time_loss_s": statistics.fmean(losses) if losses else None,
        "mean_depart_delay_s": statistics.fmean(dd) if dd else None,
        "vehicles_rerouted_at_least_once": rerouted,
        "teleports": int(tele.get("total")) if tele is not None else None,
        "loaded": int(veh.get("loaded")) if veh is not None and veh.get("loaded") is not None else None,
        "inserted": int(veh.get("inserted")) if veh is not None else None,
        "running_at_end": int(veh.get("running")) if veh is not None else None,
        "waiting_to_insert_at_end": int(veh.get("waiting")) if veh is not None else None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", choices=["static", "reactive", "predictive"], required=True)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--horizon", type=int, default=3600, help="simulation end (s)")
    p.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    p.add_argument("--compliance", type=float, default=0.3, help="fraction of equipped vehicles")
    p.add_argument("--period", type=int, default=60, help="reroute period per equipped vehicle (s)")
    p.add_argument("--weights", help="meanData XML forecast table (predictive arm)")
    p.add_argument("--net", default=str(DEFAULT_NET))
    p.add_argument("--routes", default=str(DEFAULT_ROUTES))
    p.add_argument("--edgedata-period", type=int, default=300)
    p.add_argument("--time-to-teleport", type=int, default=300)
    p.add_argument("--sumo-binary", default="sumo")
    p.add_argument("--out", help="output dir (default results/routing/<arm>_s<seed>_h<horizon>)")
    a = p.parse_args()
    if a.arm == "predictive" and not a.weights:
        p.error("--weights is required for the predictive arm")

    out = Path(a.out) if a.out else REPO / "results/routing" / f"{a.arm}_s{a.seed}_h{a.horizon}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    extra = run_static(a, out) if a.arm == "static" else run_traci(a, out)
    m = parse_metrics(out, a.horizon)
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip()
    rec = {"arm": a.arm, "seed": a.seed, "horizon_s": a.horizon, "scale": a.scale,
           "compliance": a.compliance if a.arm != "static" else 0.0, "period_s": a.period,
           "weights": a.weights, "net": str(a.net), "routes": str(a.routes),
           "sumo": subprocess.run([a.sumo_binary, "--version"], capture_output=True, text=True).stdout.split("\n")[0],
           "git": git, "wall_s": round(time.time() - t0, 1), **extra, "metrics": m}
    (out / "metrics.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
