"""sumo-web3d's own data path, unchanged: its start_sumo_executable and simulate_next_step on its cross3ltl scenario, printing
the per-step snapshot it would send over its WebSocket (vehicle creations / updates / removals, lights). Its aiohttp + websockets
server itself does not start on today's websockets (see evidence/live_twin/upstream/sumo_web3d_server_as_released.log).

    SUMO_HOME=... ~/.dhakaflow/venvs/sumo-web3d/bin/python third_party/sumo-web3d/reproduce.py
"""
import json
import os
import sys
from pathlib import Path

R = Path.home() / ".dhakaflow/upstream/sumo-web3d-d89fe8014879153d30632996f35b68efb4d8c086"
sys.path.insert(0, str(R))
import traci  # noqa: E402
traci.trafficlights = traci.trafficlight     # the alias sumo-web3d used (SUMO 1.0 era); removed in later SUMO. Their file is unchanged.
from sumo_web3d.server import server  # noqa: E402

server.start_sumo_executable(False, "--seed 1 --no-step-log", str(R / "sumo_web3d/scenarios/cross3ltl/test.sumocfg"))
counts = []
for step in range(300):
    snap = server.simulate_next_step()
    v = snap["vehicles"]
    counts.append([snap["time"], len(v["creations"]), len(v["updates"]), len(v["removals"])])
    if step in (20, 200):
        print(json.dumps({"step": step, "time": snap["time"], "first_creation": next(iter(v["creations"].items()), None),
                          "updates": len(v["updates"]), "removals": v["removals"][:5], "lights": len(snap["lights"]["updates"]) if "updates" in snap["lights"] else snap["lights"]}, default=str)[:600])
server.traci.close()
tot = [sum(c[i] for c in counts) for i in (1, 2, 3)]
print(f"300 steps: {tot[0]} vehicle creations, {tot[1]} updates, {tot[2]} removals sent as deltas")
