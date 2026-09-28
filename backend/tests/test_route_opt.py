"""The route optimizer is fed by the AnalysisRun only: unknown run -> 404, a run without a stored
forecast -> a visible refusal, a stored forecast whose hash disagrees -> refusal."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_unknown_analysis_is_404(client):
    r = client.post("/api/route/optimize", json={"analysis_run_id": "an_nope"})
    assert r.status_code == 404 and "ANALYSIS_RUN_NOT_FOUND" in r.json()["error"]
    assert client.get("/api/route/optimize/rt_nope").status_code == 404


def test_run_without_stored_forecast_is_refused(tmp_path, monkeypatch):
    from app.data import provenance
    from app.routing import analysis_routing as route_opt
    monkeypatch.setattr(provenance, "DIR", tmp_path)
    rec = {"run_id": "an_old", "horizon_min": 15, "resolved_model": "Chronos-Bolt"}
    with pytest.raises(route_opt.NoStoredForecast, match="NO_STORED_FORECAST"):
        route_opt._forecast_from_analysis(rec, 15)


def test_stored_forecast_hash_must_match():
    from app.data import provenance as pv
    from app.routing import analysis_routing as route_opt
    raw = {"15": {"c1": 2.5, "c2": 1.0}}
    rec = {"run_id": "an_x", "raw_prediction": raw, "raw_prediction_hash": pv.sha_json(raw), "forecast_unit": "congestion_level_0_3"}
    vals, unit = route_opt._forecast_from_analysis(rec, 15)
    assert vals == {"c1": 2.5, "c2": 1.0} and unit == "congestion_level_0_3"
    rec["raw_prediction_hash"] = "tampered"
    with pytest.raises(route_opt.NoStoredForecast, match="does not match"):
        route_opt._forecast_from_analysis(rec, 15)
    with pytest.raises(route_opt.NoStoredForecast, match="no forecast at horizon"):
        route_opt._forecast_from_analysis({"run_id": "an_y", "raw_prediction": raw, "raw_prediction_hash": pv.sha_json(raw)}, 60)
