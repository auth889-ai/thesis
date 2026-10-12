"""Track-based signal prediction (Bartendr): 100 m steps with their heading, the stated bin mapping, heading-matched history, the
tunnel/open-country road rule, their combination, and the strong-threshold refresh points."""
from __future__ import annotations

from core.simulation.routing import signal

NORTH = [[90.40, 23.70 + i * 0.0005] for i in range(25)]       # 24 steps of ~55 m due north = ~1.33 km


def test_steps_are_100_m_with_their_heading():
    st = signal.steps(NORTH)
    assert 12 <= len(st) <= 14 and st[0]["start_m"] == 0 and st[-1]["end_m"] >= 1300
    assert all(a["end_m"] == b["start_m"] for a, b in zip(st, st[1:]))
    assert all(abs(s["heading"]) < 1 or abs(s["heading"] - 360) < 1 for s in st) and signal.octant(st[0]["heading"]) == "0"
    assert signal.octant(180.0) == "4" and signal.octant(350.0) == "0"


def test_the_stated_mapping_to_bartendr_bins():
    assert [signal.bin_of(None, d) for d in (5.0, 2.0, 1.0, 0.5, 0.2)] == ["strong", "strong", "medium", "medium", "weak"]
    assert [signal.bin_of(t, None) for t in ("4g", "3g", "2g", "slow-2g", None)] == ["strong", "medium", "weak", "weak", "unknown"]
    assert signal.bin_of("2g", 8.0) == "strong"                                                             # a measured downlink wins


def test_history_needs_three_readings_and_uses_their_mean_downlink():
    assert signal.history_bin([])[0] == "unknown" and "in this direction" in signal.history_bin([])[1]
    assert signal.history_bin([{"n_signal": 2, "mean_downlink_mbps": 9}])[0] == "unknown"
    assert signal.history_bin([{"n_signal": 4, "mean_downlink_mbps": 0.3}, {"n_signal": 4, "mean_downlink_mbps": 0.5}])[0] == "weak"
    assert signal.history_bin([{"n_signal": 5, "mean_downlink_mbps": 1.2}])[0] == "medium"
    assert signal.history_bin([{"n_signal": 5, "weak_signal": 4, "mean_downlink_mbps": None}])[0] == "weak"


def test_road_and_history_combine():
    assert signal.road_bin([{"tunnel": True}]) == ("none", "tunnel")
    assert signal.road_bin([{"density": 1}, {"density": 2}])[0] == "weak" and signal.road_bin([{"density": 9}]) == (None, None)
    assert signal.combine(("none", "tunnel"), ("strong", "h"))["bin"] == "none"                             # a tunnel always wins
    assert signal.combine(("weak", "open country"), ("strong", "recorded history"))["bin"] == "strong"       # history beats the road's guess
    assert signal.combine(("weak", "open country"), ("unknown", "no signal history"))["bin"] == "weak"
    assert signal.combine((None, None), ("unknown", "no signal history"))["bin"] == "unknown"


def test_refresh_at_the_last_strong_step_before_each_weak_run():
    assert signal.refresh_points(["strong", "medium", "weak", "weak", "strong", "unknown", "none", "strong"]) == [0, 4]
    assert signal.refresh_points(["weak", "strong", "none"]) == [1]                                       # the first run has nothing strong before it
    assert signal.refresh_points(["medium", "weak"]) == []
