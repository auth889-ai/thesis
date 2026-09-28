"""Live traffic-state builder: binning, gap policy, ordinal encoding, floor behaviour."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from traffictwin.forecasting.live.live_state import BIN_S, LEVELS, build, features, floors, load_rows  # noqa: E402


def row(cid, t, state):
    return {"corridor_id": cid, "captured_utc": f"2026-09-01T{t}+00:00", "congestion_state": state,
            "request_latency_ms": 1.0, "google_data_mode": "RUNTIME_REFERENCE", "route_content_persisted": False}


def test_build_bins_and_ordinal_encoding():
    rows = [row("a", "10:00:10", "FREE_FLOW"), row("b", "10:00:12", "SEVERE"),
            row("a", "10:05:10", "SLOW"),      row("b", "10:05:12", "CONGESTED")]
    vals, mask, corridors, bins = build(rows)
    assert corridors == ["a", "b"] and vals.shape == (2, 2) and mask.all()
    assert vals[0, 0] == 0.0 and vals[0, 1] == 3.0 and vals[1, 0] == 1.0 and vals[1, 1] == 2.0
    assert bins[1] - bins[0] == BIN_S


def test_missing_capture_becomes_a_masked_gap_not_a_zero():
    """A gap must never look like FREE_FLOW (which is also 0.0)."""
    rows = [row("a", "10:00:10", "FREE_FLOW"), row("b", "10:00:12", "SLOW"),
            row("a", "10:10:10", "SLOW"),      row("b", "10:10:12", "SLOW")]
    vals, mask, _, _ = build(rows)
    assert vals.shape == (3, 2)
    assert not mask[1].any(), "the skipped bin must be masked"
    assert np.isnan(vals[1]).all(), "gaps are NaN, never imputed to 0"
    assert mask[0].all() and mask[2].all()


def test_unknown_and_malformed_rows_are_dropped(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        row("a", "10:00:10", "FREE_FLOW"), row("a", "10:05:10", "UNKNOWN"),
        {"corridor_id": "a"}, {"congestion_state": "SLOW"}]) + "\n\n")
    assert len(load_rows(f)) == 1


def test_features_are_dhaka_local_time():
    bins = np.array([1_756_000_000.0])                    # any epoch
    tod, dow = features(bins)[0]
    assert 0.0 <= tod < 1.0 and dow in range(7)
    local_hour = ((bins[0] + 6 * 3600) % 86400) / 3600
    assert abs(tod * 24 - local_hour) < 1e-6


def test_floors_rank_correctly_on_a_daily_pattern():
    T = 864                                               # 3 days of 5-min bins
    bins = np.arange(T) * float(BIN_S) + 1.7e9
    tod = (bins % 86400) / 86400
    vals = np.stack([np.round(2 + 1.5 * np.sin(2 * np.pi * tod)),
                     np.round(1.5 + 1.5 * np.sin(2 * np.pi * tod + 1))], 1).clip(0, 3)
    f = floors(vals, np.ones_like(vals, bool), bins, [1, 12])
    assert f[60]["historical_average"] < f[60]["global_mean"]      # pattern is learnable
    assert f[5]["persistence"] < f[5]["global_mean"]               # short horizon: persistence is strong
    assert f[60]["persistence"] > f[5]["persistence"]              # and degrades with lead time
    assert f[5]["n_pairs"] > 0


def test_floors_respect_the_mask():
    T = 300
    bins = np.arange(T) * float(BIN_S) + 1.7e9
    vals = np.random.RandomState(0).uniform(0, 3, (T, 2))
    mask = np.ones_like(vals, bool)
    mask[T // 2:, :] = False                              # everything after the split is a gap
    f = floors(vals, mask, bins, [1])
    assert f[5]["n_pairs"] == 0 and f[5]["persistence"] is None
