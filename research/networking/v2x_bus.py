"""V2X control-message bus (thin adapter over the official stack's behaviour).

Messages from the AI planner do NOT act directly: each ControlMessage is
queued with a delivery latency sampled from the distribution MEASURED in the
reproduced official Eclipse MOSAIC example (artifacts/gates/mosaic_barnim/
latencies.json). Only on delivery does an actuator adapter execute the action
through legitimate SUMO physics APIs:

  EXTEND_GREEN   -> trafficlight.setPhaseDuration   (signal controller)
  SPEED_TARGET   -> vehicle.slowDown (smooth decel/accel over 5 s — CAV)
  ROUTE_ADVISORY -> vehicle.rerouteTraveltime (measured costs — nav client)

Never moveTo, never teleport, never deletion. Every message logs
send_t, latency_ms, delivery_t, ack, executed — the AI -> NETWORK ->
ACTUATOR -> MOBILITY chain is fully traceable.

Full MOSAIC coupling of the Dhaka scenario (scenario-convert) is the declared
integration follow-up; this bus is the minimum honest adapter, calibrated by
the official stack, never a homemade network simulator.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LATENCY_FILE = REPO / "artifacts/gates/mosaic_barnim/latencies.json"


class V2XBus:
    def __init__(self, seed: int = 0, latency_file: Path = LATENCY_FILE):
        lat = json.loads(Path(latency_file).read_text())
        self.samples_ms = lat["latencies_ms"]
        self.source = lat["source"]
        self.rng = random.Random(seed)
        self.queue: list[dict] = []      # pending
        self.log: list[dict] = []        # everything, delivered or not
        self._id = 0

    def send(self, sim_t: float, mtype: str, target: str, payload: dict):
        self._id += 1
        lat_ms = self.rng.choice(self.samples_ms)
        m = {"msg_id": self._id, "type": mtype, "target": target,
             "payload": payload, "sent_s": round(sim_t, 1),
             "latency_ms": round(lat_ms, 1),
             "deliver_s": round(sim_t + lat_ms / 1000.0, 3),
             "ack": False, "executed": False}
        self.queue.append(m)
        self.log.append(m)
        return m["msg_id"]

    def deliver_due(self, t, sim_t: float):
        """Execute every message whose network delivery time has arrived."""
        due = [m for m in self.queue if m["deliver_s"] <= sim_t]
        self.queue = [m for m in self.queue if m["deliver_s"] > sim_t]
        for m in due:
            try:
                if m["type"] == "EXTEND_GREEN":
                    t.trafficlight.setPhaseDuration(
                        m["target"], float(m["payload"]["extend_s"]))
                elif m["type"] == "ADVANCE_PHASE":
                    t.trafficlight.setPhaseDuration(m["target"], 0.0)
                elif m["type"] == "SPEED_TARGET":
                    t.vehicle.slowDown(m["target"],
                                       float(m["payload"]["speed_m_s"]), 5.0)
                elif m["type"] == "ROUTE_ADVISORY":
                    t.vehicle.rerouteTraveltime(m["target"])
                m["ack"] = True
                m["executed"] = True
            except Exception as e:                 # noqa: BLE001
                m["ack"] = False
                m["error"] = str(e)[:80]
        return due

    def dump(self, path: Path):
        path.write_text(json.dumps(
            {"transport_model": self.source,
             "messages": self.log,
             "sent": len(self.log),
             "delivered": sum(1 for m in self.log if m["executed"])},
            indent=1))
