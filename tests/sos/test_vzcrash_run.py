"""research/sos/vzcrash/run.py (step M, phase 3): the pure parts on synthetic arrays; no dataset file is needed or allowed on the laptop."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("vz_run", REPO / "research/sos/vzcrash/run.py")
vz = importlib.util.module_from_spec(spec); sys.modules["vz_run"] = vz; spec.loader.exec_module(vz)


def event(peak_g: float, at_s: float = 8.0, seconds: int = 16, speed_kmh: float | None = 50.0):
    n = seconds * vz.RATE_HZ
    acc = np.zeros((n, 3), "float32"); acc[:, 2] = 1.0
    k = int(at_s * vz.RATE_HZ); acc[k, 0] = peak_g              # |a| = sqrt(peak^2 + 1)
    gps = np.full(seconds, np.nan if speed_kmh is None else speed_kmh, "float32")
    return acc, gps


def test_the_rule_matches_the_apps_rule_on_synthetic_events():
    acc, gps = event(5.0)
    r = vz.wreckwatch(acc, gps)
    assert r["detected"] and r["at_s"] == 8.0 and abs(r["peak_g"] - np.sqrt(26)) < 1e-4 and r["speed_known"]
    slow = vz.wreckwatch(acc, np.full(16, 10.0, "float32"))                    # 5 g but under 15 mph: no alarm, and it says why
    assert not slow["detected"] and slow["over_4g_but_slow"]
    nospeed = vz.wreckwatch(*event(5.0, speed_kmh=None))                        # no GPS: the speed check is not made, as in the app
    assert nospeed["detected"] and not nospeed["speed_known"]
    assert not vz.wreckwatch(*event(2.0))["detected"]                           # a 2 g brake stays under 4 g
    sp = vz.speed_per_sample(np.array([10.0, 30.0]), 250)
    assert sp[0] == 10.0 and sp[99] == 10.0 and sp[100] == 30.0 and np.isnan(sp[200])


def test_the_authors_baseline_is_the_peak_horizontal_norm_without_the_gravity_axis():
    acc, gps = event(5.0)
    acc[200, 1] = 3.0; acc[300, 2] = 9.0                                        # a y spike and a big z spike (z is gravity's axis: ignored)
    assert vz.baseline_score(acc, None, gps) == pytest.approx(5.0)
    acc[400, 0] = 3.0; acc[400, 1] = 4.0                                        # sqrt(3^2 + 4^2) = 5 ties the x peak; a 6 beats it
    acc[500, 1] = 6.0
    assert vz.baseline_score(acc, None, gps) == pytest.approx(6.0)
    assert vz.BASELINE["name"].startswith("peak horizontal acceleration")


def test_the_saved_instance_results_are_untouched_and_the_baseline_matches_the_paper():
    """The numbers fetched from the instance (evidence/sos/vzcrash/) still hash as the instance wrote them, and the authors' baseline
    reproduces the paper's Table I (AP 89.62 % on the test split) before anything of ours is read next to it."""
    import hashlib, json
    d = REPO / "evidence/sos/vzcrash"
    if not (d / "SHA256SUMS").exists():
        pytest.skip("no VZCrash results fetched")
    for line in (d / "SHA256SUMS").read_text().splitlines():
        h, name = line.split()
        assert hashlib.sha256((d / name).read_bytes()).hexdigest() == h, name
    r = json.loads((d / "results.json").read_text())
    assert r["dataset"]["revision"] == "42e1482d005c0e545379d6cfa4939486c9fe4249" and r["dataset"]["limit"] is None
    assert abs(r["A_physical_baseline"]["test"]["ap"] - 0.8962) < 0.0005                  # paper, Table I: 89.62 %
    b = r["B_wreckwatch_rule"]["test"]
    assert b["n_pos"] + b["n_neg"] == r["dataset"]["events_test"] and 0 < b["recall_on_crashes"] < 1


def test_features_and_pr_points():
    acc, gps = event(5.0)
    f = vz.features(acc, np.zeros((len(acc), 3), "float32"), gps)
    assert len(f) == len(vz.FEATURES) == 14 and f[1] == 5.0 and f[7] == 1 and f[9] == 50.0
    scores = np.array([0.9, 0.8, 0.7, 0.6]); y = np.array([1, 1, 0, 1])
    pr = vz.pr_points(scores, y)
    assert pr["precision"][0] == 1.0 and pr["recall"][-1] == 1.0
    assert pr["ap"] == pytest.approx((1 / 3) * 1.0 + (1 / 3) * 1.0 + (1 / 3) * 0.75)
    m = vz.rule_metrics(np.array([True, False, True, False]), np.array([1, 1, 0, 0]), np.array(["crash", "crash", "near_miss", "normal_driving"]))
    assert m["recall_on_crashes"] == 0.5 and m["false_alarm_rate_negatives"] == 0.5 and m["fired_rate_near_miss"] == 1.0 and m["fired_rate_normal_driving"] == 0.0
