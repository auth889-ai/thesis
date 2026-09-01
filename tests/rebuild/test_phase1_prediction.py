"""Phase-1 prediction: provenance completeness, unit correctness, and the gate logic itself."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from predict.comparison_table import FLOOR_NAMES, build, gate  # noqa: E402
from predict.record_results import MAPE_IS_FRACTION, PUBLISHED, UPSTREAM, parse_log  # noqa: E402

RES = REPO / "predict/results"
PY = sys.executable


# ------------------------------------------------------------------ units and parsing
def test_mape_is_converted_from_fraction_to_percent(tmp_path):
    """The harness logs MAPE as a fraction; shipping 0.07 as '0.07 %' would be a 100x error."""
    log = tmp_path / "GWNet_METR-LA.log"
    log.write_text("NUM_EPOCHS: 50\nEpoch 50 / 50\n"
                   "horizon 3, Test MAE: 2.7190, Test MAPE: 0.0702, Test RMSE: 5.1830\n")
    r = parse_log(log, {"gpu": "T4"})
    assert MAPE_IS_FRACTION
    row = r["metrics_by_horizon_min"][15]
    assert row["mape_pct"] == pytest.approx(7.02, abs=0.01), "must be percent, not the raw fraction"
    assert row["mae"] == pytest.approx(2.719)


def test_epochs_are_parsed_from_the_real_log_format(tmp_path):
    log = tmp_path / "STID_METR-LA.log"
    log.write_text("NUM_EPOCHS: 50\nEpoch 49 / 50\nEpoch 50 / 50\n"
                   "horizon 3, Test MAE: 2.8, Test MAPE: 0.077, Test RMSE: 5.5\n")
    r = parse_log(log, {})
    assert r["epochs"] == 50 and r["epochs_completed"] == 50


def test_published_diff_is_computed_against_the_paper(tmp_path):
    log = tmp_path / "GWNet_METR-LA.log"
    log.write_text("horizon 3, Test MAE: 2.690, Test MAPE: 0.069, Test RMSE: 5.150\n")
    row = parse_log(log, {})["metrics_by_horizon_min"][15]
    assert row["published_mae"] == PUBLISHED[("GWNet", "METR-LA")][15][0]
    assert row["mae_diff_pct"] == pytest.approx(0.0, abs=0.01), "identical to published means 0 % diff"


def test_upstream_provenance_is_complete():
    assert len(UPSTREAM["harness"]["sha"]) == 40, "the harness must be pinned by full SHA"
    for name, m in UPSTREAM["models"].items():
        assert m["repo"].startswith("https://") and m["paper"], name


# ------------------------------------------------------------------ the gate itself
def _rows(city, trained_mae, floor_mae, diff=1.0):
    rows = [{"dataset": city, "kind": "floor", "model": f, "horizon_min": h, "mae": floor_mae,
             "rmse": 1.0, "mape_pct": 1.0, "published_mae": None, "mae_diff_pct": None, "trained": False}
            for f in ("persistence", "historical_average") for h in (15, 30, 60)]
    rows += [{"dataset": city, "kind": "trained", "model": m, "horizon_min": h, "mae": trained_mae,
              "rmse": 1.0, "mape_pct": 1.0, "published_mae": 2.69, "mae_diff_pct": diff, "trained": True}
             for m in ("STID", "GWNet") for h in (15, 30, 60)]
    return rows


def test_gate_passes_only_when_every_condition_holds():
    rows = _rows("METR-LA", 2.7, 3.4) + _rows("PEMS-BAY", 1.3, 1.6)
    inf = {("GWNet", "METR-LA"): {"window_mae_all_horizons_mph": 3.0}}
    g = gate(rows, inf)
    assert g["passed"], g["checks"]


def test_gate_fails_when_a_model_does_not_beat_the_floors():
    rows = _rows("METR-LA", 5.0, 3.4) + _rows("PEMS-BAY", 1.3, 1.6)      # trained worse than floor
    g = gate(rows, {("GWNet", "METR-LA"): {"window_mae_all_horizons_mph": 3.0}})
    assert not g["passed"] and not g["checks"]["G4_models_beat_floors"]["ok"]


def test_gate_fails_when_reproduction_is_far_from_published():
    rows = _rows("METR-LA", 2.7, 3.4, diff=45.0) + _rows("PEMS-BAY", 1.3, 1.6, diff=45.0)
    g = gate(rows, {("GWNet", "METR-LA"): {"window_mae_all_horizons_mph": 3.0}})
    assert not g["checks"]["G5_gwnet_reproduces_published"]["ok"]


def test_gate_fails_without_checkpoint_inference():
    rows = _rows("METR-LA", 2.7, 3.4) + _rows("PEMS-BAY", 1.3, 1.6)
    g = gate(rows, {})
    assert not g["checks"]["G6_checkpoint_inference"]["ok"], "a metrics table is not a usable model"


def test_gate_fails_with_only_one_city():
    g = gate(_rows("METR-LA", 2.7, 3.4), {("GWNet", "METR-LA"): {"window_mae_all_horizons_mph": 3.0}})
    assert not g["checks"]["G1_both_cities"]["ok"]


# ------------------------------------------------------------------ the real artefacts
@pytest.mark.skipif(not (RES / "trained_results.json").exists(), reason="no trained results yet")
def test_real_record_carries_full_provenance():
    doc = json.loads((RES / "trained_results.json").read_text())
    for r in doc["runs"]:
        assert r["harness"]["sha"] and r["config"] and r["epochs_completed"]
        assert r["hardware"]["instance_type"] and r["hardware"]["gpu"]
        assert r["dataset"] in UPSTREAM["datasets"]
        for _, row in r["metrics_by_horizon_min"].items():
            assert 0 < row["mae"] < 50 and 0 < row["mape_pct"] < 100, "MAPE must be a percent"


@pytest.mark.skipif(not (RES / "phase1_comparison.json").exists(), reason="run comparison_table.py")
def test_comparison_table_is_regenerable_and_self_consistent():
    r = subprocess.run([PY, str(REPO / "predict/comparison_table.py")], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr[-500:]
    doc = json.loads((RES / "phase1_comparison.json").read_text())
    assert doc["rows"] and "gate" in doc
    for row in doc["rows"]:
        assert row["kind"] in ("floor", "trained")
        assert row["mae"] is None or row["mae"] > 0
