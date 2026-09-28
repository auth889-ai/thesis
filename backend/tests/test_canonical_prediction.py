"""The scientific web path delegates to the controller's service, not headline files."""
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from traffictwin.forecasting import ForecastService, ModelSpec
from traffictwin.forecasting.operations import road_forecasts, scientific_prediction


@pytest.fixture
def service(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"test checkpoint")
    spec = ModelSpec("GWNet", "METR-LA", str(checkpoint), hashlib.sha256(checkpoint.read_bytes()).hexdigest()[:16],
                     2, (1, 12, 2, 1), (1, 12, 2, 1), (15, 30, 60), {}, {}, {},
                     "FORECAST_VALIDATED", "PUBLIC_BENCHMARK_ONLY")
    instance = ForecastService.__new__(ForecastService)
    instance.spec, instance.card = spec, {}
    instance.raw = np.arange(80, dtype="float32").reshape(40, 2, 1) + 1
    instance.values = instance.raw[:, :, 0].astype("float64")
    calls = []
    def predict(card, as_of):
        calls.append(as_of)
        return np.repeat(instance.raw[as_of - 1, :, 0][None], 12, axis=0) + 1
    instance._bt = SimpleNamespace(predict=predict)
    monkeypatch.setattr(ForecastService, "metr_la_gwnet", lambda: instance)
    return instance, calls


def test_map_predictions_are_fresh_and_share_controller_hashes(service):
    instance, calls = service
    expected = instance.predict(25)
    for _ in range(2):
        now, pred, info = road_forecasts._predict("METR_LA", 25, "GWNet")
        np.testing.assert_array_equal(pred, expected["prediction"])
        assert info["input_window_hash"] == expected["input_window_hash"]
        assert info["raw_prediction_hash"] == expected["raw_prediction_hash"]
        assert len(info["checkpoint_sha256"]) == 64
        assert info["prediction_cache_hit"] is False and info["inference_recomputed"] is True
    assert calls == [25, 25, 25]


@pytest.mark.parametrize("as_of", [-1, 11, 41, True, 12.5, "25"])
def test_service_rejects_invalid_windows_instead_of_silent_clamping(service, as_of):
    instance, calls = service
    with pytest.raises(ValueError):
        instance.predict(as_of)
    assert calls == []


def test_latest_window_uses_last_observation_without_rewinding(service):
    instance, calls = service
    result = instance.predict(40)
    assert result["as_of"] == 40 and calls == [40]
    np.testing.assert_array_equal(result["now"], instance.values[-1])


def test_checkpoint_mismatch_fails_before_inference(service):
    from pathlib import Path
    instance, calls = service
    Path(instance.spec.checkpoint_path).write_bytes(b"different checkpoint")
    with pytest.raises(RuntimeError, match="checkpoint"):
        instance.predict(25)
    assert calls == []


def test_unexpected_forecast_shape_is_rejected(service):
    instance, _ = service
    instance._bt.predict = lambda *_: np.ones((12, 3))
    with pytest.raises(RuntimeError, match="shape"):
        instance.predict(25)


def test_existing_nonfinite_replacement_is_disclosed(service):
    instance, _ = service
    instance._bt.predict = lambda *_: np.full((12, 2), np.nan)
    result = instance.predict(25)
    assert result["nonfinite_values_replaced"] == 24
    np.testing.assert_array_equal(result["prediction"][0], instance.values[24])


def test_persistence_does_not_call_learned_model(service):
    instance, calls = service
    now, pred, info = scientific_prediction.forecast(25, "persistence")
    assert calls == []
    np.testing.assert_array_equal(pred, np.repeat(now[None], 12, axis=0))
    assert info["checkpoint_sha256"] is None
    assert info["result_source"] == "COMPUTED_BASELINE"


def test_unknown_model_cannot_fall_back_silently(service):
    with pytest.raises(ValueError, match="supports"):
        scientific_prediction.forecast(25, "not-a-model")


def test_partial_future_is_not_filled_or_indexed_past_end(service, monkeypatch):
    instance, _ = service
    meta = {"name": "test", "nodes": ["S0", "S1"], "quantity": "speed mph", "interval_s": 300,
            "first_utc": "2012-03-01T00:00:00", "coords": []}
    monkeypatch.setattr(road_forecasts, "_series", lambda _: (meta, instance.values))
    monkeypatch.setattr(road_forecasts, "_mapping", lambda _: None)
    result = road_forecasts.network("METR_LA", 39)
    assert all(value is None for value in result["sensors"][0]["actual"].values())
    road = road_forecasts.road("METR_LA", "S0", 39)
    assert len(road["actual"]) == 1
    assert road["models"]["GWNet"]["abs_error_by_h"] == {}


def test_legacy_prediction_cache_is_explicit(monkeypatch):
    from traffictwin.data import forecast_inputs
    from traffictwin.forecasting.operations import model_registry
    monkeypatch.setattr(model_registry, "resolve", lambda *_: {"model": "persistence"})
    monkeypatch.setattr(road_forecasts, "_PRED", {})
    calls = []
    def compute(*args):
        calls.append(args)
        return np.ones(2), np.ones((12, 2)), {}
    monkeypatch.setattr(forecast_inputs, "forecast_all", compute)
    first = road_forecasts._predict("user:example", 25, "persistence")[2]
    second = road_forecasts._predict("user:example", 25, "persistence")[2]
    assert len(calls) == 1
    assert first["prediction_cache_hit"] is False
    assert second["prediction_cache_hit"] is True and second["inference_recomputed"] is False
    assert second["result_source"] == "CACHED_INFERENCE"


def test_prediction_job_uses_canonical_adapter_not_legacy_series(service, tmp_path, monkeypatch):
    from traffictwin.forecasting.operations import prediction_jobs
    from traffictwin.data import provenance
    instance, calls = service
    monkeypatch.setattr(scientific_prediction, "series", lambda: ({"first_utc": "2012-03-01T00:00:00"}, instance.values))
    monkeypatch.setattr(prediction_jobs, "_series", lambda *_: pytest.fail("legacy path called"))
    monkeypatch.setattr(prediction_jobs, "_JOBS", {"test": {}})
    monkeypatch.setattr(provenance, "DIR", tmp_path)
    prediction_jobs._run("test", {"dataset": "METR_LA", "model": "GWNet", "as_of": 25, "region": 0})
    result = prediction_jobs.status("test")
    assert result["status"] == "done", result
    assert calls == [25]
    assert result["result"]["forecast_contract"]["dataset"] == "METR-LA"
    assert result["result"]["provenance"]["inference_recomputed"] is True


def test_cloud_configuration_check_uses_public_credential_loader(monkeypatch):
    from traffictwin.common import credentials
    from traffictwin.forecasting.operations import prediction_jobs
    for name in prediction_jobs.AWS_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(credentials, "load", lambda _: "")
    assert prediction_jobs._aws_env() is None
