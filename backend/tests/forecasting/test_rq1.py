"""RQ1 building blocks on toy series with known answers (docs/PAPER_MAP.md, RQ1)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.ml.forecasting.transfer_dhaka import baselines, character, transfer
from core.ml.forecasting.transfer_dhaka.dhaka import persistence, windows


def test_weekday_table_averages_same_weekday_and_slot_and_ignores_outages():
    ts = pd.date_range("2024-01-01", periods=288 * 14, freq="5min")                 # two weeks from a Monday
    x = np.zeros((len(ts), 2))
    x[:, 0] = ts.dayofweek.values * 10 + 1                                           # each weekday its own level
    x[:, 1] = np.where(ts.hour < 6, 0, 50)                                           # outages before 06:00
    t = baselines.weekday_table(x, ts)
    assert t[0, 0, 0] == 1.0 and t[6, 100, 0] == 61.0
    assert np.isnan(t[0, 0, 1]) and t[2, 200, 1] == 50.0
    pred = baselines.predict_weekday(t, ts, np.array([0]), context=288, steps=2, fallback=np.full((1, 2, 2), -1.0))
    assert pred[0, 0, 0] == 11.0 and pred[0, 0, 1] == -1.0                          # Tuesday 00:00; no reading -> the fallback, never 0


def test_basicts_metrics_match_protocol_b_scorer():
    """In its own process: torch and the tree libraries crash when they share one (Protocol B isolates them the same way)."""
    import subprocess
    import sys
    code = """
import numpy as np
from core.ml.forecasting.transfer_dhaka.metrics import score
from core.ml.forecasting.evaluation.protocol_b.scoring import score as pb
rng = np.random.default_rng(0)
y = rng.uniform(20, 70, (50, 12, 10)); y[0, 2, 3] = 0
p = y + rng.normal(0, 3, y.shape)
a, b = score(p, y), pb(p, y, np.full(10, 30.0))
assert all(a[h] == {k: b[h][k] for k in ("mae", "rmse", "mape_pct")} for h in (15, 30, 60)), (a, b)
print("same")
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "same" in r.stdout, r.stderr[-800:]


def test_character_measures_on_known_series():
    t = np.arange(156)
    smooth = character.measures(50 + 10 * np.sin(t / 20))
    jumpy = character.measures(np.where(t % 2 == 0, 40.0, 10.0))
    assert smooth["stop_and_go_share"] == 0.0 and smooth["acf_1"] > 0.99
    assert jumpy["stop_and_go_share"] == 1.0 and jumpy["acf_1"] == pytest.approx(-1.0) and jumpy["cv"] == pytest.approx(0.6)


def test_transfer_is_unit_free_and_trains_only_on_what_it_is_given():
    """In its own process: in the full suite torch is already loaded and xgboost then hangs (the same isolation as above)."""
    import subprocess
    import sys
    code = """
import numpy as np
from core.ml.forecasting.transfer_dhaka import transfer
rng = np.random.default_rng(1)
base = 50 + 10 * np.sin(np.arange(3000) / 40)
train = np.stack([base, base * 0.5], 1) + rng.normal(0, 1, (3000, 2))
m = transfer.fit(train, seed=11, n_fit=3000)
ctx = np.stack([base[2000:2012] * 0.2] * 3)[:, :, None].astype("float32")     # another city at a fifth of the speed
p = transfer.predict(m, ctx, 12)
assert abs(p["xgboost"][0, 2, 0] - base[2014] * 0.2) < 1.0, p["xgboost"][0, 2, 0]
assert set(transfer.CANNOT_TRANSFER) == {"DCRNN", "GWNet", "MegaCRN", "STAEformer", "STID", "D2STGNN"}
print("ok")
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-800:]


def test_dhaka_windows_need_a_full_context_and_persistence_holds_the_last_value():
    v = np.array([np.nan, 10, 11, 12, 13] + list(range(14, 40)), dtype=float)[:, None]
    ctx, truth, origins = windows(v, context=3, steps=2)
    assert origins[0] == 3 and ctx.shape[1:] == (3, 1) and truth.shape[1:] == (2, 1)
    assert persistence(ctx, 2)[0, :, 0].tolist() == [12.0, 12.0]


def test_findings_quote_the_tables_own_numbers():
    from core.ml.forecasting.transfer_dhaka.summary import findings
    cell = lambda m: {"15": {"mae": m - 1}, "30": {"mae": m - .5}, "60": {"mae": m}}
    lab = {"METR-LA": {"persistence": cell(4.9), "xgboost": cell(4.1), "timesfm": cell(4.3), "chronos2": cell(4.4)}}
    dk = {"persistence": cell(3.1), "chronos2": cell(3.4)}
    tr = {"xgboost_trained_on_metr_la": cell(2.2), "xgboost_trained_on_pems_bay": cell(2.0)}
    f = findings(lab, dk, tr, {})
    assert "XGBoost at 4.1 mph" in f["lab"][0] and "against 4.9 for persistence" in f["lab"][0] and "TimesFM 2.5 (zero-shot) at 4.3" in f["lab"][0]
    assert "at 60 minutes Chronos-2 (zero-shot) 3.4 km/h against persistence 3.1 (not better)" in f["lab"][1]
    assert "2.2 mph" in f["unseen_city"] and "against 2.0" in f["unseen_city"] and "10.0 %" in f["unseen_city"]


def test_endpoint_says_plainly_when_rq1_has_not_run(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.forecasting.routers import rq1 as r
    from app.main import app
    monkeypatch.setattr(r, "OUT", tmp_path)
    c = TestClient(app)
    assert c.get("/api/forecasting/rq1").json()["available"] is False
    (tmp_path / "summary.json").write_text('{"findings": {"lab": ["x"]}}')
    assert c.get("/api/forecasting/rq1").json() == {"available": True, "findings": {"lab": ["x"]}}
    assert c.get("/api/forecasting/rq1/figures/summary.json").status_code == 404
