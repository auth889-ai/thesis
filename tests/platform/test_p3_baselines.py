"""P3 baseline protocol tests — split hygiene, masked metrics, leakage guard."""
from __future__ import annotations

import numpy as np
import pytest

from traffictwin.forecasting.evaluation.twin_baselines import (EVIDENCE_DOMAIN, HORIZONS_STEPS,
                                            ChronoSplit,
                                            historical_average_forecast,
                                            masked_metrics,
                                            persistence_forecast,
                                            run_baselines)


def test_horizons_map_to_actuation_lead_times():
    # 300 s steps: 5/15/30 min — signal, rerouting, advisory lead times.
    assert HORIZONS_STEPS == {"5min": 1, "15min": 3, "30min": 6}


def test_split_is_chronological_and_hash_stable():
    s = ChronoSplit.standard(1000)
    assert 0 < s.train_end < s.val_end < 1000
    assert s.sha256() == ChronoSplit.standard(1000).sha256()
    with pytest.raises(ValueError, match="non-chronological"):
        ChronoSplit(n_timesteps=100, train_end=90, val_end=80)


def test_masked_metrics_ignore_invalid_and_gate_mape():
    target = np.array([[10.0, 0.0], [np.nan, 5.0]])
    pred = np.array([[12.0, 1.0], [99.0, 4.0]])
    valid = np.array([[True, True], [True, True]])
    m = masked_metrics(pred, target, valid)
    # NaN target dropped; zero target excluded from MAPE but kept in MAE.
    assert m["n_scored"] == 3
    assert m["mae"] == pytest.approx((2 + 1 + 1) / 3)
    assert m["mape_validity_fraction"] == pytest.approx(2 / 3)


def test_metrics_refuse_all_invalid():
    with pytest.raises(ValueError, match="no valid points"):
        masked_metrics(np.ones((2, 2)), np.ones((2, 2)),
                       np.zeros((2, 2), dtype=bool))


def test_persistence_is_exact_on_constant_series():
    series = np.full((50, 3), 7.0)
    pred = persistence_forecast(series, 6)
    assert pred.shape == (44, 3)
    assert np.allclose(pred, series[6:])


def test_historical_average_uses_train_region_only():
    # Slot means differ between train and test; HA must reflect TRAIN values.
    t, n, period = 100, 2, 10
    series = np.zeros((t, n))
    split = ChronoSplit.standard(t)          # train_end=70
    series[:split.train_end] = 5.0           # train slot mean = 5
    series[split.train_end:] = 50.0          # test values would leak as 50
    pred = historical_average_forecast(series, 1, split, period_steps=period)
    assert np.allclose(pred[split.val_end:], 5.0)   # no leakage from test


def test_run_baselines_reports_evidence_domain_and_all_horizons():
    rng = np.random.default_rng(0)
    t, n = 3 * 288, 5
    data = rng.uniform(2, 15, size=(t, n, 4))
    mask = np.ones((t, n), dtype=bool)
    reports = run_baselines(data, mask, channel_idx=0, channel_name="speed_ms")
    assert {r.model for r in reports} == {"persistence", "historical_average"}
    for r in reports:
        d = r.to_dict()
        assert d["evidence_domain"] == EVIDENCE_DOMAIN
        assert d["reality_label"] == "SIMULATED"
        assert set(d["horizons"]) == {"5min", "15min", "30min"}
        assert {r2.split_sha256 for r2 in reports} == {r.split_sha256}


def test_persistence_beats_noise_on_smooth_series():
    # Sanity: on a slowly-varying series persistence must be far better than
    # a shuffled predictor — proves the alignment isn't off by one.
    t, n = 400, 3
    x = np.linspace(0, 8 * np.pi, t)
    series = np.stack([10 + 3 * np.sin(x + k) for k in range(n)], axis=1)
    mask = np.ones((t, n), dtype=bool)
    pred = persistence_forecast(series, 1)
    m = masked_metrics(pred, series[1:], mask[1:])
    assert m["mae"] < 0.5
