"""Federated forecasting mechanics: FedAvg, RSU partition, byte accounting, measured-link sampling."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.forecasting.federated_forecast import Link, fedavg, measured_link, model_bytes, partition_sensors  # noqa: E402


def test_partition_is_a_true_partition():
    for n, k in ((207, 8), (325, 16), (250, 3), (10, 10)):
        parts = partition_sensors(n, k)
        flat = [i for p in parts for i in p]
        assert sorted(flat) == list(range(n)), "every sensor exactly once"
        assert all(parts), "no empty RSU"


def test_spatial_partition_groups_neighbours():
    """Two tight, far-apart clusters must not be mixed into one RSU."""
    rng = np.random.default_rng(0)
    coords = np.vstack([rng.normal(0, 0.01, (50, 2)), rng.normal(10, 0.01, (50, 2))])
    parts = partition_sensors(100, 2, coords)
    assert sorted(i for p in parts for i in p) == list(range(100))
    for p in parts:
        assert max(p) < 50 or min(p) >= 50, "an RSU spans both distant clusters"


def test_fedavg_matches_the_published_rule():
    a, b = {"w": np.array([0.0, 10.0])}, {"w": np.array([10.0, 0.0])}
    assert np.allclose(fedavg([(a, 1), (b, 1)])["w"], [5.0, 5.0])
    assert np.allclose(fedavg([(a, 3), (b, 1)])["w"], [2.5, 7.5])       # sample-size weighted
    assert np.allclose(fedavg([(a, 7)])["w"], a["w"])                    # single client is identity
    with pytest.raises(ValueError):
        fedavg([])


def test_byte_accounting_is_float32_volume():
    assert model_bytes({"a": np.zeros((10, 10)), "b": np.zeros(5)}) == 420
    assert model_bytes({}) == 0


@pytest.fixture(scope="module")
def stats():
    try:
        return measured_link()
    except SystemExit as ex:
        pytest.skip(str(ex))


def test_link_statistics_come_from_real_mosaic_runs(stats):
    assert stats["sources"] >= 1 and stats["n_messages"] > 1000
    assert 0.5 < stats["delivery_ratio"] <= 1.0
    assert np.isclose(stats["latency_weights"].sum(), 1.0)
    assert 1.0 < stats["latency_ms_bins"].mean() < 1000.0


def test_sampled_delivery_matches_the_measured_ratio(stats):
    link = Link(stats, seed=1)
    got = np.mean([link.send(1000)[0] for _ in range(4000)])
    assert abs(got - stats["delivery_ratio"]) < 0.03


def test_injected_loss_and_latency_move_the_right_way(stats):
    base = Link(stats, seed=2)
    b_del = np.mean([base.send(1)[0] for _ in range(2000)])
    b_lat = np.mean([base.send(1)[1] for _ in range(2000)])
    lossy = Link(stats, seed=2, extra_loss=0.3)
    assert np.mean([lossy.send(1)[0] for _ in range(2000)]) < b_del - 0.2
    slow = Link(stats, seed=2, extra_latency_ms=500)
    assert np.mean([slow.send(1)[1] for _ in range(500)]) > b_lat + 400
    assert Link(stats, seed=2, extra_loss=5.0).loss == 1.0               # clamped, never > 1
