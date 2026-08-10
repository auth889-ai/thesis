from __future__ import annotations
import csv
import os
import sys
from pathlib import Path


def ensure_sumo_tools():
    sumo_home = os.environ.get("SUMO_HOME")
    candidates = [sumo_home, "/usr/share/sumo", "/usr/local/share/sumo"]
    for base in candidates:
        if base and Path(base, "tools").exists():
            tools = str(Path(base, "tools"))
            if tools not in sys.path:
                sys.path.insert(0, tools)
            os.environ["SUMO_HOME"] = base
            return base
    raise RuntimeError("SUMO_HOME/tools not found. Install `sumo sumo-tools` in Colab.")


IN_LANES = {
    "NS": ["N_in_0", "S_in_0"],
    "EW": ["E_in_0", "W_in_0"],
}
OUT_LANES = {
    "NS": ["S_out_0", "N_out_0"],
    "EW": ["W_out_0", "E_out_0"],
}
GREEN_PHASE = {"NS": 0, "EW": 3}
YELLOW_PHASE = {"NS": 1, "EW": 4}


def lane_queue(traci, lane_ids):
    return sum(traci.lane.getLastStepHaltingNumber(lane) for lane in lane_ids)


def pressure(traci, axis):
    return lane_queue(traci, IN_LANES[axis]) - lane_queue(traci, OUT_LANES[axis])


def sample_state(traci, tls_id="J0"):
    return {
        "time": traci.simulation.getTime(),
        "phase": traci.trafficlight.getPhase(tls_id),
        "ns_in_queue": lane_queue(traci, IN_LANES["NS"]),
        "ew_in_queue": lane_queue(traci, IN_LANES["EW"]),
        "ns_pressure": pressure(traci, "NS"),
        "ew_pressure": pressure(traci, "EW"),
        "vehicles": traci.vehicle.getIDCount(),
    }


def run_traci(config, strategy, out_dir, seed=2018, max_time=5000):
    ensure_sumo_tools()
    import traci

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tripinfo = out_dir / "tripinfo.xml"
    summary = out_dir / "summary.xml"
    queue_csv = out_dir / "queue_timeseries.csv"
    cmd = [
        "sumo",
        "-c",
        str(config),
        "--seed",
        str(seed),
        "--tripinfo-output",
        str(tripinfo),
        "--summary-output",
        str(summary),
        "--no-step-log",
        "true",
    ]
    traci.start(cmd)
    rows = []
    try:
        strategy.reset(traci)
        while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < max_time:
            traci.simulationStep()
            strategy.step(traci)
            rows.append(sample_state(traci))
    finally:
        traci.close()
    with queue_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["time"])
        writer.writeheader()
        writer.writerows(rows)
    return tripinfo, summary, queue_csv
