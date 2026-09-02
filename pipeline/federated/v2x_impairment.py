#!/usr/bin/env python3
"""A THIN communication-impairment adapter for official federated forecasting code.

This is the point where networking is made to affect learning, and it is deliberately the only
thing we add: the learning algorithm, the model, the data pipeline and the aggregation rule all
stay exactly as the original authors wrote them. We wrap the transport, nothing else.

    from pipeline.federated import v2x_impairment
    meter = v2x_impairment.install(profile="mosaic_v2x", role="client", seed=1)
    ...                                     # upstream code runs untouched
    meter.dump(Path("run.json"))

HOW IT ATTACHES
    FedGTP's server and clients talk over real TCP sockets through two classes with a clean
    send/recv chokepoint (`lib/server_socket.ServerSocket`, `lib/client_socket.ClientSocket`), and
    `send()` already returns the payload length. We monkey-patch those four methods at import time
    from our own launcher. The upstream working tree is never modified, so its pinned SHA stays
    meaningful and `git status` in the clone stays clean.

WHAT THE PROFILES MEAN — and what they are NOT
    Every profile here is a SIMULATED impairment. The `mosaic_v2x` latency distribution is drawn
    from Eclipse MOSAIC's SNS ad-hoc ITS-G5 model — an official simulator — not from measurements
    on radio hardware. No claim about real-world V2X timing is made or implied by these numbers.

    ideal        no added delay, no loss. The control condition.
    mosaic_v2x   per-message delay sampled from the MOSAIC ITS-G5 latency distribution.
    latency_*    a fixed added one-way delay, to isolate delay from loss.
    loss_*       a fixed probability that a model update misses its deadline.

WHAT "PACKET LOSS" MEANS FOR A MODEL UPDATE
    These are TCP sockets, so bytes are not silently dropped; what a real deployment loses is an
    update that does not arrive before the round closes. The upstream server blocks until it has
    received from every client (`assert len(rcvd_msgs) == self.n_clients`), so simply not sending
    would deadlock rather than degrade. We model a missed deadline the way a straggler is handled
    in practice: the sender's PREVIOUS payload is transmitted again, so the aggregator combines a
    stale contribution instead of a fresh one, and the event is counted in `dropped_updates`.
    Round one has no previous payload, so a drop there is counted and the fresh value is sent —
    recorded as `drops_before_cache` so the number is never quietly wrong.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOSAIC_LATENCIES = REPO / "artifacts/gates/mosaic_barnim/latencies.json"


@dataclass
class Profile:
    name: str
    added_latency_ms: float = 0.0      # fixed one-way delay added to every message
    sample_mosaic: bool = False        # draw the delay from the MOSAIC ITS-G5 distribution instead
    loss_prob: float = 0.0             # probability an update misses its round deadline
    note: str = ""


PROFILES = {
    "ideal":        Profile("ideal", note="control: no added delay, no loss"),
    "mosaic_v2x":   Profile("mosaic_v2x", sample_mosaic=True,
                            note="delay sampled from the simulated MOSAIC ITS-G5 distribution"),
    "latency_50":   Profile("latency_50", added_latency_ms=50),
    "latency_200":  Profile("latency_200", added_latency_ms=200),
    "latency_1000": Profile("latency_1000", added_latency_ms=1000),
    "loss_10":      Profile("loss_10", loss_prob=0.10),
    "loss_30":      Profile("loss_30", loss_prob=0.30),
    "loss_50":      Profile("loss_50", loss_prob=0.50),
    "mosaic_loss_10": Profile("mosaic_loss_10", sample_mosaic=True, loss_prob=0.10,
                              note="the simulated V2X delay profile plus a 10 % missed-deadline rate"),
}


@dataclass
class Meter:
    profile: str = "ideal"
    role: str = "?"
    seed: int = 0
    messages_sent: int = 0
    bytes_sent: int = 0
    dropped_updates: int = 0
    drops_before_cache: int = 0
    added_delay_s: float = 0.0
    delays_ms: list = field(default_factory=list)
    started_utc: str = ""
    wall_s: float = 0.0
    latency_source: str = ""
    _t0: float = 0.0

    def dump(self, path: Path) -> None:
        self.wall_s = round(time.time() - self._t0, 3) if self._t0 else 0.0
        d = asdict(self)
        d.pop("_t0", None)
        ds = d.pop("delays_ms")
        if ds:
            s = sorted(ds)
            d["delay_ms_mean"] = round(sum(s) / len(s), 3)
            d["delay_ms_p50"] = round(s[len(s) // 2], 3)
            d["delay_ms_p95"] = round(s[int(len(s) * 0.95)], 3)
            d["delay_ms_max"] = round(s[-1], 3)
        d["added_delay_s"] = round(d["added_delay_s"], 3)
        d["measurement_nature"] = ("SIMULATED impairment; the mosaic_v2x latency distribution "
                                   "comes from an official simulator, not radio hardware")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d, indent=1))


def _mosaic_samples() -> tuple[list[float], str]:
    if not MOSAIC_LATENCIES.exists():
        raise SystemExit(f"MOSAIC latency profile missing at {MOSAIC_LATENCIES}; "
                         f"run the Barnim gate first")
    d = json.loads(MOSAIC_LATENCIES.read_text())
    for key in ("latencies_ms", "samples_ms", "latency_ms"):
        if key in d:
            return list(d[key]), d.get("source", str(MOSAIC_LATENCIES))
    raise SystemExit(f"no latency sample list in {MOSAIC_LATENCIES}: keys={list(d)}")


def install(profile: str, role: str, seed: int = 0, repo_on_path: Path | None = None) -> Meter:
    """Wrap the upstream socket classes. Returns the meter that records what the link did."""
    if profile not in PROFILES:
        raise SystemExit(f"unknown profile {profile!r}; have {sorted(PROFILES)}")
    p = PROFILES[profile]
    rng = random.Random(seed)
    meter = Meter(profile=profile, role=role, seed=seed,
                  started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    meter._t0 = time.time()

    samples: list[float] = []
    if p.sample_mosaic:
        samples, src = _mosaic_samples()
        meter.latency_source = src
    else:
        meter.latency_source = f"fixed {p.added_latency_ms} ms" if p.added_latency_ms else "none"

    def delay_ms() -> float:
        if p.sample_mosaic and samples:
            return rng.choice(samples) + p.added_latency_ms
        return p.added_latency_ms

    import sys
    if repo_on_path and str(repo_on_path) not in sys.path:
        sys.path.insert(0, str(repo_on_path))
    from lib.client_socket import ClientSocket           # noqa: E402  (upstream, path set above)
    from lib.server_socket import ServerSocket           # noqa: E402

    cache: dict = {}

    def wrap(cls) -> None:
        original = cls.send

        def send(self, msg, *args, **kwargs):
            key = (id(self), args[0] if args else kwargs.get("conn"))
            if p.loss_prob and rng.random() < p.loss_prob:
                meter.dropped_updates += 1
                if key in cache:
                    msg = cache[key]           # missed deadline -> aggregate the stale payload
                else:
                    meter.drops_before_cache += 1
            else:
                cache[key] = msg
            d = delay_ms()
            if d:
                time.sleep(d / 1000.0)
                meter.added_delay_s += d / 1000.0
                meter.delays_ms.append(d)
            n = original(self, msg, *args, **kwargs)
            meter.messages_sent += 1
            meter.bytes_sent += int(n or 0)
            return n

        send.__doc__ = f"impairment-wrapped {cls.__name__}.send (profile {p.name})"
        cls.send = send

    wrap(ClientSocket)
    wrap(ServerSocket)
    return meter
