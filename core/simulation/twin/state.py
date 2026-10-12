"""Generate one current SUMO state for identical-state controller branches."""
import argparse
import hashlib
import time
from pathlib import Path
from core.common.paths import REPO
from core.simulation.twin import runtime as pr

def state_content_hash(path: Path) -> str:
    """SHA-256 of a SUMO state file's CONTENT: the <!-- generated on … --> header and the
    <configuration> block (file paths, timestamps) are skipped, so two identical simulation states
    saved at different times or under different directories hash the same."""
    txt = path.read_text()
    i = txt.find("<snapshot")                       # everything before it is SUMO's commented-out configuration echo (paths, port, timestamp)
    body = txt[i:] if i >= 0 else txt
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def save_fork_state(seed: int, routes: Path, out: Path, P: dict, caps: dict, event_hook=None) -> tuple[Path, str]:
    """The baseline prefix: run from departure to fork_t0_s with the caps (and any incident already
    started) applied, save ONE SUMO state including pending vehicles and the RNG, hash it."""
    import traci
    out.mkdir(parents=True, exist_ok=True)
    t_fork = int(P["fork_t0_s"]); state = out / f"fork_state_s{seed}_t{t_fork}.xml"
    if state.exists():
        if P.get("strict_fresh"):
            raise RuntimeError("Fresh execution refuses an existing fork state")
        return state, state_content_hash(state)
    ns = argparse.Namespace(net=str(REPO / P["network"]), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"], edgedata_period=300, time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--route-steps", "0", "--save-state.rng", "true"]
    traci.start(cmd, port=pr.free_port(), label=f"prefix-{seed}-{time.time()}")
    lanes = {e: [f"{e}_{i}" for i in range(traci.edge.getLaneNumber(e))] for e in caps if e in traci.edge.getIDList()}
    def apply(t_now):
        for edge, steps in caps.items():
            cap = next((c for tf, c in reversed(steps) if tf <= t_now), steps[0][1])
            for inc in (P.get("incident") or []):
                if inc["edge"] == edge and t_now >= inc["t_start_s"]:
                    cap = min(cap, float(inc["cap_mps"]))
            for lid in lanes.get(edge, []):
                traci.lane.setMaxSpeed(lid, cap)
        for inc in (P.get("incident") or []):
            if t_now >= inc["t_start_s"] and inc["edge"] not in caps:
                for lid in [f"{inc['edge']}_{i}" for i in range(traci.edge.getLaneNumber(inc["edge"]))]:
                    traci.lane.setMaxSpeed(lid, float(inc["cap_mps"]))
    apply(0); t = 0
    while t < t_fork:
        traci.simulationStep(); t = int(traci.simulation.getTime())
        if event_hook and t % 30 == 0:
            positions = []
            for vid in sorted(traci.vehicle.getIDList())[:50]:
                lon, lat = traci.simulation.convertGeo(*traci.vehicle.getPosition(vid))
                positions.append({"vehicle_id": vid, "lon": lon, "lat": lat, "edge": traci.vehicle.getRoadID(vid)})
            event_hook({"type": "simulation", "sim_time_s": t, "active_vehicles": traci.vehicle.getIDCount(), "positions": positions})
        if t % 300 == 0 or any(t == int(i["t_start_s"]) for i in (P.get("incident") or [])):
            apply(t)
    traci.simulation.saveState(str(state))
    traci.close()
    return state, state_content_hash(state)

