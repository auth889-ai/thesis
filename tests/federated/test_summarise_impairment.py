"""The impairment table is the thesis's headline result, so its arithmetic is tested against a
fixture rather than first exercised on a run that took GPU hours to produce."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "src/traffictwin/forecasting/federated/summarise_impairment.py"


def _run(tmp_out: Path):
    """Run the summariser against a redirected results directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("summarise_impairment", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.OUT = tmp_out
    return mod


def _fixture(out: Path, runs):
    out.mkdir(parents=True, exist_ok=True)
    (out / "fedgtp_impairment_PeMSD7.json").write_text(json.dumps(
        {"upstream_sha": "ff128f5", "dataset": "PeMSD7", "runs": runs}))


def _run_rec(profile, mae, *, bytes_=1000, dropped=0, status="OK", drops_before=0):
    return {"profile": profile, "dataset": "PeMSD7", "status": status, "epochs": 5, "clients": 4,
            "wall_s": 10.0, "upstream": {"sha": "ff128f5"},
            "forecast": None if mae is None else {"mae": mae, "rmse": mae * 2, "mape": mae / 2},
            "communication": {"total_bytes": bytes_, "total_messages": 20,
                              "dropped_updates": dropped, "drops_before_cache": drops_before,
                              "added_delay_s_total": 0.0, "delay_ms_p95": None}}


def test_degradation_is_measured_against_the_same_method(tmp_path):
    mod = _run(tmp_path)
    _fixture(tmp_path, [_run_rec("ideal", 2.0), _run_rec("loss_30", 2.5)])
    rows = mod.collect()
    mod.add_degradation(rows)
    by = {r["profile"]: r for r in rows}
    assert by["ideal"]["mae_vs_ideal_pct"] == 0.0
    assert by["loss_30"]["mae_vs_ideal_pct"] == 25.0, "2.0 -> 2.5 is a 25 % degradation"


def test_a_method_is_never_compared_against_another_methods_baseline(tmp_path):
    """A run with no ideal baseline of its own must report no degradation, not borrow one."""
    mod = _run(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "fedgtp_impairment_PeMSD7.json").write_text(json.dumps(
        {"dataset": "PeMSD7", "runs": [_run_rec("ideal", 2.0)]}))
    (tmp_path / "cnfgnn_impairment_PeMSD7.json").write_text(json.dumps(
        {"dataset": "PeMSD7", "runs": [_run_rec("loss_30", 9.0)]}))
    rows = mod.collect()
    mod.add_degradation(rows)
    cn = next(r for r in rows if r["method"] == "cnfgnn")
    assert cn["mae_vs_ideal_pct"] is None, "cnfgnn has no ideal run; it must not use fedgtp's"


def test_missing_forecast_is_reported_not_invented(tmp_path):
    mod = _run(tmp_path)
    _fixture(tmp_path, [_run_rec("ideal", 2.0), _run_rec("loss_30", None, status="FAILED")])
    rows = mod.collect()
    mod.add_degradation(rows)
    bad = next(r for r in rows if r["profile"] == "loss_30")
    assert bad["mae"] is None and bad["mae_vs_ideal_pct"] is None
    assert bad["status"] == "FAILED"


def test_markdown_flags_failed_runs_and_uncached_drops(tmp_path, monkeypatch):
    mod = _run(tmp_path)
    _fixture(tmp_path, [_run_rec("ideal", 2.0),
                        _run_rec("loss_30", None, status="FAILED"),
                        _run_rec("loss_10", 2.2, dropped=5, drops_before=2)])
    monkeypatch.setattr(sys, "argv", ["summarise_impairment.py", "--quiet"])
    assert mod.main() == 0
    md = (tmp_path / "impairment.md").read_text()
    assert "Runs that did not complete" in md, "a failed run must be visible, not dropped"
    assert "no cached predecessor" in md.lower()
    assert "SIMULATED" in md, "the table must never imply the impairments were measured"


def test_exits_nonzero_when_there_is_nothing_to_summarise(tmp_path, monkeypatch):
    mod = _run(tmp_path / "empty")
    monkeypatch.setattr(sys, "argv", ["summarise_impairment.py", "--quiet"])
    assert mod.main() == 1, "an empty results dir must fail loudly, not write an empty table"
