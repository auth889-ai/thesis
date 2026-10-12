"""Second TraCI client (order 2) on the SUMO that Veins (order 1) forked: the feasibility spike (2026-10-12).
Runs on SUMO 1.21's own traci (~/.dhakaflow/venvs/sumo-veins). Steps in lockstep with Veins, writes a parameter on a vehicle and a
traffic light every 10 simulated seconds and reads it back, and records what it saw in spike_client.json."""
import json
import os
import sys
import time

import sumo
sys.path.insert(0, os.path.join(sumo.SUMO_HOME, "tools"))
import traci  # noqa: E402

port = int(sys.argv[1]); out = sys.argv[2]
t0 = time.time()
traci.init(port=port, numRetries=120, label="ml")
traci.setOrder(2)
rec = {"sumo_version": traci.getVersion(), "steps": 0, "params_written": 0, "params_read_back_ok": 0, "times": [], "tls": traci.trafficlight.getIDList(), "max_vehicles": 0, "errors": []}
last_mark = -1
while traci.simulation.getMinExpectedNumber() > 0 or traci.simulation.getTime() < 700:
    traci.simulationStep(traci.simulation.getTime() + 1.0)            # the same 1 s cadence as Veins's updateInterval
    rec["steps"] += 1
    t = traci.simulation.getTime()
    ids = traci.vehicle.getIDList(); rec["max_vehicles"] = max(rec["max_vehicles"], len(ids))
    if int(t) % 10 == 0 and int(t) != last_mark:
        last_mark = int(t); rec["times"].append(t)
        try:
            if ids:
                traci.vehicle.setParameter(ids[0], "ml.flag", f"set@{t:g}"); rec["params_written"] += 1
                rec["params_read_back_ok"] += traci.vehicle.getParameter(ids[0], "ml.flag") == f"set@{t:g}"
            for tl in rec["tls"]:
                traci.trafficlight.setParameter(tl, "ml.preempt", "0"); rec["params_written"] += 1
                rec["params_read_back_ok"] += traci.trafficlight.getParameter(tl, "ml.preempt") == "0"
        except Exception as e:                                        # noqa: BLE001
            rec["errors"].append(f"{t}: {e!r}")
    if t >= 719:
        break
rec["end_time"] = traci.simulation.getTime(); rec["wall_s"] = round(time.time() - t0, 1)
try:
    traci.close()
except Exception as e:                                                # noqa: BLE001
    rec["errors"].append(f"close: {e!r}")
json.dump(rec, open(out, "w"), indent=1)
print("CLIENT2", json.dumps({k: v for k, v in rec.items() if k != "times"}), flush=True)
