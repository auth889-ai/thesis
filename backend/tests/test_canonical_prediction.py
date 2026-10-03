"""The scientific web path delegates to the controller's service, not headline files."""
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from app.forecasting import ForecastService, ModelSpec
from app.forecasting.operations import road_forecasts, scientific_prediction


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


def test_prediction_is_recomputed_on_every_request(monkeypatch):
    """No stored answers: two identical requests are two forward passes, each labelled FRESH_INFERENCE."""
    from app.data import forecast_inputs
    from app.forecasting.operations import model_registry
    monkeypatch.setattr(model_registry, "resolve", lambda *_: {"model": "persistence"})
    calls = []
    def compute(*args):
        calls.append(args)
        return np.ones(2), np.ones((12, 2)), {}
    monkeypatch.setattr(forecast_inputs, "forecast_all", compute)
    first = road_forecasts._predict("user:example", 25, "persistence")[2]
    second = road_forecasts._predict("user:example", 25, "persistence")[2]
    assert len(calls) == 2
    assert first["result_source"] == second["result_source"] == "FRESH_INFERENCE"
    assert not first["prediction_cache_hit"] and second["inference_recomputed"]
    assert not hasattr(road_forecasts, "_PRED")


def test_prediction_job_uses_canonical_adapter_not_legacy_series(service, tmp_path, monkeypatch):
    from app.forecasting.operations import prediction_jobs
    from app.data import provenance
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
    from app import credentials
    from app.forecasting.operations import prediction_jobs
    for name in prediction_jobs.AWS_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(credentials, "load", lambda _: "")
    assert prediction_jobs._aws_env() is None


def test_aws_job_script_applies_the_same_python312_fix_as_the_local_path():
    """DCRNN's official config calls random.randint with float bounds; Python >= 3.10 raises. The local
    trainer patches it to integer bounds; the AWS job script must do the same or the cloud run dies at import
    (job dcrnn-metr-la, 2026-10-02, died in six minutes)."""
    from app.forecasting.training.aws import scripts
    from app.forecasting.training import basicts_train
    import inspect
    assert "random.randint(-1000000, 1000000)" in scripts.BENCHMARK_SCRIPT if hasattr(scripts, "BENCHMARK_SCRIPT") else "random.randint(-1000000, 1000000)" in inspect.getsource(scripts)
    assert "random.randint(-1000000, 1000000)" in inspect.getsource(basicts_train)


def test_protocol_b_scores_the_trained_checkpoints_with_the_official_architecture():
    """Protocol B (evaluate_models) must include every trained checkpoint it can find, loaded through the
    pinned harness's config, never a local re-implementation; names must match the leaderboard's."""
    import inspect
    from app.forecasting.evaluation import checkpoint_stage, evaluate_models
    assert checkpoint_stage.ARCH == {"GraphWaveNet": "GWNet", "STID": "STID", "STAEformer": "STAEformer", "DCRNN": "DCRNN", "D2STGNN": "D2STGNN", "MegaCRN": "MegaCRN"}
    src = inspect.getsource(checkpoint_stage)
    assert "load_official_cfg" in src and "find_checkpoints" in src
    assert "the harness data file and the evaluation data file disagree" in src   # the timeline check stays
    assert '"checkpoints"' in inspect.getsource(evaluate_models.stage)
    assert "checkpoints_for(dataset)" in inspect.getsource(evaluate_models.evaluate)
    for ck in checkpoint_stage.checkpoints_for("METR-LA"):
        assert "best_val" in ck["path"].name and ck["dataset_dir"] == "METR-LA"


def test_regime_aware_conformal_restores_coverage_where_a_global_quantile_cannot():
    """Residuals that are small in free flow and large in congestion: one global 90 % quantile over-covers
    free flow and under-covers congestion; a quantile per prediction-time regime covers both. MAPIE owns
    the quantile; our estimator is the identity on the stored point forecast."""
    import numpy as np
    from app.forecasting.evaluation import conformal
    rng = np.random.default_rng(0)
    n = 4000
    cong = rng.random(n) < 0.3
    scale = np.where(cong, 8.0, 1.0)
    pred = rng.uniform(20, 60, n)
    y_cal, y_te = pred + rng.normal(0, scale), pred + rng.normal(0, scale)
    g = conformal._quantile_model(pred, y_cal)
    lo, hi = conformal._interval(g, pred)
    cov_global_cong = ((y_te >= lo) & (y_te <= hi))[cong].mean()
    lo_r, hi_r = np.empty(n), np.empty(n)
    for c in (False, True):
        m = conformal._quantile_model(pred[cong == c], y_cal[cong == c])
        lo_r[cong == c], hi_r[cong == c] = conformal._interval(m, pred[cong == c])
    cov_regime_cong = ((y_te >= lo_r) & (y_te <= hi_r))[cong].mean()
    cov_regime_all = ((y_te >= lo_r) & (y_te <= hi_r)).mean()
    assert cov_global_cong < 0.8                       # the global quantile is set by the easy regime
    assert 0.86 <= cov_regime_cong <= 0.94 and 0.86 <= cov_regime_all <= 0.94


def test_protocol_b_merge_refuses_a_stage_scored_on_different_windows(tmp_path, monkeypatch):
    """A foundation model's predictions join the persisted block only if they were made on exactly the
    same windows; otherwise the comparison would silently mix test moments."""
    import numpy as np
    from app.forecasting.evaluation import evaluate_models as em
    monkeypatch.setattr(em, "OUT", tmp_path)
    monkeypatch.setattr(em, "load", lambda ds: np.ones((1000, 4), dtype="float32"))
    (tmp_path / "protocol_b").mkdir()
    np.savez_compressed(tmp_path / "protocol_b/X_val_w3_n4_s1.npz", truth=np.ones((3, 12, 4)), starts=np.array([10, 11, 12]), threshold=np.ones(4))
    bad = tmp_path / "bad.npz"
    np.savez_compressed(bad, truth=np.ones((3, 12, 4)), starts=np.array([20, 21, 22]), pred_m=np.ones((3, 12, 4)))
    with pytest.raises(SystemExit):
        em.merge("X", "val", 3, 4, 1, [bad])
    good = tmp_path / "good.npz"
    np.savez_compressed(good, truth=np.ones((3, 12, 4)), starts=np.array([10, 11, 12]), pred_m=np.ones((3, 12, 4)))
    assert em.merge("X", "val", 3, 4, 1, [good]) is None                      # the validation block is never a comparison record
    assert "pred_m" in np.load(tmp_path / "protocol_b/X_val_w3_n4_s1.npz").files


def test_finish_runs_the_same_commands_a_reviewer_would(monkeypatch, tmp_path):
    """`--finish` is a sequence of the public commands, in order; no private scoring path."""
    import inspect
    from app.forecasting.training.aws import benchmark, cli
    src = inspect.getsource(benchmark.finish)
    for must in ("collect(a, job)", "collect_checkpoints(a, job)", '"--stage", "checkpoints"', '"--merge"', "app.forecasting.evaluation.conformal"):
        assert must in src, must
    assert "--finish" in inspect.getsource(cli.parser)
    from app.forecasting.training import basicts_train
    from app.forecasting.operations import model_registry
    for arch in ("D2STGNN", "MegaCRN"):
        assert arch in basicts_train.ARCHS and arch in model_registry.TRAINED


def test_checkpoint_stage_never_hands_a_model_the_future_speed():
    """Models whose official forward takes future covariates (MegaCRN's time of day) get them; the speed
    channel of that tensor is zeroed in the source, so the stage cannot leak the answer."""
    import inspect
    from app.forecasting.evaluation import checkpoint_stage
    src = inspect.getsource(checkpoint_stage.predict_checkpoints)
    assert "f[..., 0] = 0.0" in src and "future_data=torch.tensor(f)" in src


def test_forecast_map_serves_every_trained_checkpoint_with_fresh_inference(client):
    """Any architecture with a best-validation METR-LA checkpoint is selectable on the forecast map; the
    answer carries a fresh forward pass, the checkpoint's SHA-256 and the loader it came through."""
    from app.forecasting.operations import served_checkpoints as sc, scientific_prediction as sp
    served = sc.available("METR-LA")
    if not served:
        pytest.skip("no trained checkpoints collected on this machine")
    groups = {g["key"]: [i["model"] for i in g["items"]] for g in sp.registry("METR_LA")["groups"]}
    assert set(groups["trained"]) == set(served) - {"GWNet"}
    name = sorted(set(served) - {"GWNet"})[0]
    now, pred, info = sp.forecast(20000, name)
    assert pred.shape == (12, 207) and info["result_source"] == "FRESH_INFERENCE" and len(info["checkpoint_sha256"]) == 64
    assert info["forecast_contract"]["loader"].startswith("official config")
    r = client.get(f"/api/forecast-map/METR_LA/road?node=S3&as_of=20000&models={name},persistence")
    assert r.status_code == 200
    with pytest.raises(ValueError):
        sp.forecast(20000, "NotAModel")
