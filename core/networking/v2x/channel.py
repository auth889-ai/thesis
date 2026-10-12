"""SIMULATED V2X COMMUNICATION — a deterministic message channel between SUMO vehicles and the
traffic-management server. Not radio hardware, not a 5G/DSRC stack: an emulator with real queueing
semantics (creation time, scheduled delivery, latency, jitter, drop probability, TTL, expiry) whose
every event is logged and measurable.

    up   = Channel("uplink",   seed=1, latency_ms=50, jitter_ms=20, loss=0.05, ttl_s=30)
    up.send(t_now, {"type": "VEHICLE_STATUS", "vehicle_id": "veh12", ...})
    for msg in up.deliver(t_now):          # only messages whose delivery time has come
        server.receive(msg)

The latency profile can also be sampled from the official Eclipse MOSAIC Barnim example
(results/artifacts/gates/mosaic_barnim/latencies.json, SIMULATED ITS-G5), so the "ideal" and "mosaic"
profiles rest on that reproduced run rather than on a guess.
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from core.common.paths import REPO
MOSAIC_LATENCIES = REPO / "results/artifacts/gates/mosaic_barnim/latencies.json"

PROFILES = {                       # name -> (latency_ms, jitter_ms, loss, ttl_s)
    "ideal":      (0.0,    0.0,  0.00, 60.0),
    "mosaic":     ("mosaic", 0.0, 0.00, 60.0),      # latency sampled from the reproduced MOSAIC run
    "lat100":     (100.0,  20.0, 0.00, 60.0),
    "lat500":     (500.0,  50.0, 0.00, 60.0),
    "lat1000":    (1000.0, 100.0, 0.00, 60.0),
    "lat5000":    (5000.0, 500.0, 0.00, 60.0),
    "loss05":     (50.0,   20.0, 0.05, 60.0),
    "loss10":     (50.0,   20.0, 0.10, 60.0),
    "loss20":     (50.0,   20.0, 0.20, 60.0),
    "degraded":   (500.0,  100.0, 0.30, 60.0),
}


class Channel:
    def __init__(self, name: str, seed: int = 0, latency_ms: float | str = 0.0, jitter_ms: float = 0.0, loss: float = 0.0, ttl_s: float = 60.0,
                 latency_file: Path = MOSAIC_LATENCIES):
        self.name, self.seed = name, seed
        self.latency_ms, self.jitter_ms, self.loss, self.ttl_s = latency_ms, float(jitter_ms), float(loss), float(ttl_s)
        self.rng = random.Random(f"{name}:{seed}")
        self.samples = None
        if latency_ms == "mosaic":
            d = json.loads(Path(latency_file).read_text())
            self.samples, self.latency_source = d["latencies_ms"], d.get("source")
        else:
            self.latency_source = "configured"
        self.queue: list[dict] = []
        self.log: list[dict] = []          # every message ever sent, with its fate
        self._n = 0
        self.bytes_tx = 0
        self.expiry_from_creation = False
        self.event_hook = None

    def emit(self, event, env, t):
        if self.event_hook:
            self.event_hook({**env, "type": event, "sim_time_s": t, "vehicle_id": env["payload"].get("vehicle_id")})

    @classmethod
    def from_profile(cls, name: str, profile: str, seed: int = 0) -> "Channel":
        lat, jit, loss, ttl = PROFILES[profile]
        return cls(name, seed, lat, jit, loss, ttl)

    def _latency(self) -> float:
        base = self.rng.choice(self.samples) if self.samples is not None else float(self.latency_ms)
        jit = self.rng.uniform(-self.jitter_ms, self.jitter_ms) if self.jitter_ms else 0.0
        return max(0.0, base + jit)

    def send(self, t_now: float, msg: dict) -> dict:
        """Queue a message at simulation time t_now. Returns the envelope (dropped or scheduled)."""
        self._n += 1
        size = len(json.dumps(msg, separators=(",", ":")).encode())
        self.bytes_tx += size
        env = {"msg_id": f"{self.name}-{self._n}", "channel": self.name, "type": msg.get("type"), "to": msg.get("to"), "from": msg.get("from"),
               "created_s": round(float(t_now), 3), "size_bytes": size, "payload": msg, "status": "QUEUED", "latency_ms": None, "delivered_s": None}
        if self.rng.random() < self.loss:
            env["status"] = "DROPPED"
        else:
            lat = self._latency()
            env["latency_ms"] = round(lat, 2)
            env["deliver_at_s"] = round(float(t_now) + lat / 1000.0, 3)
            origin = min(float(t_now), float(msg.get("created_s", t_now))) if self.expiry_from_creation else env["deliver_at_s"]
            env["expires_s"] = round(origin + self.ttl_s, 3)
            self.queue.append(env)
        self.log.append(env)
        self.emit("V2X_TX", env, t_now)
        return env

    def deliver(self, t_now: float) -> list[dict]:
        """Every queued message whose delivery time has arrived (and that has not expired)."""
        out, keep = [], []
        for env in self.queue:
            if self.expiry_from_creation and t_now > env["expires_s"]:
                env["status"] = "EXPIRED"
                self.emit("V2X_EXPIRED", env, t_now)
            elif env["deliver_at_s"] <= t_now:
                if t_now > env["expires_s"]:
                    env["status"] = "EXPIRED"
                else:
                    env["status"] = "DELIVERED"; env["delivered_s"] = round(float(t_now), 3); out.append(env)
                    env["observed_latency_ms"] = round((float(t_now) - env["created_s"]) * 1000, 3)
                self.emit("V2X_RX" if env["status"] == "DELIVERED" else "V2X_EXPIRED", env, t_now)
            else:
                keep.append(env)
        self.queue = keep
        return out

    def expire_all(self, t_now: float) -> None:
        for env in self.queue:
            env["status"] = "UNDELIVERED_AT_END"
            self.emit("V2X_UNDELIVERED", env, t_now)
        self.queue = []

    def metrics(self, duration_s: float | None = None) -> dict:
        tx = len(self.log); rx = sum(1 for e in self.log if e["status"] == "DELIVERED")
        dropped = sum(1 for e in self.log if e["status"] == "DROPPED"); expired = sum(1 for e in self.log if e["status"] == "EXPIRED")
        lats = sorted(e["latency_ms"] for e in self.log if e["status"] == "DELIVERED")
        observed = sorted(e.get("observed_latency_ms", e["latency_ms"]) for e in self.log if e["status"] == "DELIVERED")
        q = lambda p: (lats[min(len(lats) - 1, int(p * len(lats)))] if lats else None)
        return {"channel": self.name, "latency_profile": {"latency_ms": self.latency_ms, "jitter_ms": self.jitter_ms, "loss": self.loss, "ttl_s": self.ttl_s, "source": self.latency_source},
                "messages_tx": tx, "messages_rx": rx, "messages_dropped": dropped, "messages_expired": expired, "undelivered_at_end": sum(1 for e in self.log if e["status"] == "UNDELIVERED_AT_END"),
                "packet_delivery_ratio": round(rx / tx, 4) if tx else None, "latency_mean_ms": round(statistics.fmean(lats), 2) if lats else None,
                "latency_median_ms": q(0.5), "latency_p95_ms": q(0.95), "latency_p99_ms": q(0.99),
                "observed_latency_median_ms": observed[min(len(observed) - 1, int(.5 * len(observed)))] if observed else None,
                "observed_latency_p95_ms": observed[min(len(observed) - 1, int(.95 * len(observed)))] if observed else None,
                "bytes_tx": self.bytes_tx, "message_rate_per_s": round(tx / duration_s, 3) if duration_s else None, "throughput_bytes_per_s": round(self.bytes_tx / duration_s, 1) if duration_s else None}


def connected(vid: str, penetration: float, seed: int) -> bool:
    """Deterministic connected-vehicle assignment: the same vehicle is connected in every arm of a
    seed, and a fraction `penetration` of the population is connected."""
    import hashlib
    h = int(hashlib.sha256(f"{seed}:{vid}".encode()).hexdigest()[:8], 16)
    return (h % 10_000) < penetration * 10_000
