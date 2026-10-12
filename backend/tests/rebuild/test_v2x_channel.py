"""The simulated V2X channel: deterministic, latency delays delivery, loss drops messages, TTL expires
them, penetration selects a stable connected population, and metrics come from the message log."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from core.networking.v2x.channel import PROFILES, Channel, connected  # noqa: E402


def test_latency_delays_delivery_until_the_scheduled_time():
    ch = Channel("down", seed=1, latency_ms=500.0, jitter_ms=0.0, loss=0.0, ttl_s=60)
    env = ch.send(10.0, {"type": "ROUTE_RECOMMENDATION", "to": "v1", "vehicle_id": "v1"})
    assert env["status"] == "QUEUED" and env["deliver_at_s"] == pytest.approx(10.5)
    assert ch.deliver(10.0) == [] and ch.deliver(10.4) == []             # not yet
    got = ch.deliver(10.5)
    assert len(got) == 1 and got[0]["status"] == "DELIVERED" and got[0]["latency_ms"] == 500.0
    assert ch.deliver(11.0) == []                                          # delivered once only


def test_packet_loss_drops_messages_deterministically_and_they_never_arrive():
    a = Channel("down", seed=7, latency_ms=0.0, loss=0.5, ttl_s=1e6); b = Channel("down", seed=7, latency_ms=0.0, loss=0.5, ttl_s=1e6)
    fa = [a.send(t, {"type": "X", "to": f"v{t}"})["status"] for t in range(200)]
    fb = [b.send(t, {"type": "X", "to": f"v{t}"})["status"] for t in range(200)]
    assert fa == fb                                                        # same seed, same fate
    dropped = fa.count("DROPPED"); assert 60 <= dropped <= 140
    delivered = a.deliver(500.0)
    assert len(delivered) == 200 - dropped and all(e["status"] == "DELIVERED" for e in delivered)
    m = a.metrics(200.0)
    assert m["messages_tx"] == 200 and m["messages_dropped"] == dropped and m["messages_rx"] == 200 - dropped
    assert m["packet_delivery_ratio"] == pytest.approx((200 - dropped) / 200)


def test_ttl_expires_late_messages_and_metrics_count_them():
    ch = Channel("down", seed=3, latency_ms=100.0, loss=0.0, ttl_s=5.0)
    ch.send(0.0, {"type": "X", "to": "v1"})
    assert ch.deliver(20.0) == []                                          # arrived at 0.1 s, nobody polled until 20 s: expired
    m = ch.metrics()
    assert m["messages_expired"] == 1 and m["messages_rx"] == 0


def test_profiles_and_jitter_are_bounded():
    for name in PROFILES:
        ch = Channel.from_profile("up", name, seed=5)
        envs = [ch.send(0.0, {"type": "S", "to": "TMS"}) for _ in range(50)]
        lat, jit, loss, ttl = PROFILES[name]
        for e in envs:
            if e["status"] == "QUEUED":
                assert e["deliver_at_s"] >= 0 and e["expires_s"] == pytest.approx(e["deliver_at_s"] + ttl)
                if lat != "mosaic":
                    assert abs(e["latency_ms"] - lat) <= jit + 1e-9
    ideal = Channel.from_profile("up", "ideal", seed=1).send(1.0, {"type": "S", "to": "TMS"})
    assert ideal["latency_ms"] == 0.0 and ideal["status"] == "QUEUED"


def test_penetration_selects_a_stable_fraction_and_zero_means_nobody():
    ids = [f"veh{i}" for i in range(2000)]
    for p in (0.1, 0.3, 0.5, 1.0):
        n = sum(connected(v, p, seed=101) for v in ids)
        assert abs(n / 2000 - p) < 0.04, (p, n)
    assert not any(connected(v, 0.0, 101) for v in ids)
    assert [connected(v, 0.3, 101) for v in ids[:50]] == [connected(v, 0.3, 101) for v in ids[:50]]     # identical in every arm of a seed
    assert [connected(v, 0.3, 101) for v in ids[:200]] != [connected(v, 0.3, 102) for v in ids[:200]]   # but a different draw per seed


def test_metrics_are_computed_from_the_message_log_not_configured_values():
    ch = Channel("down", seed=2, latency_ms=100.0, jitter_ms=50.0, loss=0.0, ttl_s=1e6)
    for t in range(20):
        ch.send(float(t), {"type": "X", "to": "v"})
    ch.deliver(500.0)
    m = ch.metrics(20.0)
    lats = [e["latency_ms"] for e in ch.log]
    assert m["latency_median_ms"] == sorted(lats)[10] and 50 <= m["latency_mean_ms"] <= 150 and m["message_rate_per_s"] == 1.0
    assert m["bytes_tx"] == sum(e["size_bytes"] for e in ch.log)
