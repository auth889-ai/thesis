"""Web adapter for the controller's METR-LA ForecastService; no prediction cache."""
import hashlib
import json
from pathlib import Path
import threading
from datetime import datetime, timedelta

import numpy as np

from traffictwin.forecasting import ForecastService, ModelRegistry
from traffictwin.paths import REPO
from traffictwin.orchestration.scenario import REFERENCE

DATASETS = {"METR_LA", "METR-LA"}
_LOCK = threading.Lock()


def mapping() -> dict:
    protocol = json.loads((REPO / "results/v2x/closed_loop" / REFERENCE / "report.json").read_text())["protocol"]
    path = REPO / protocol["mapping_file"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not digest.startswith(protocol["mapping_hash"]):
        raise RuntimeError("Scenario A mapping does not match frozen evidence")
    result = json.loads(path.read_text())
    result["file"], result["file_hash"] = protocol["mapping_file"], digest
    result["records"] = [{"opposite_edge": None, **r, "node": f"S{r['node_index']}"} for r in result["records"]]
    return result


def series():
    from traffictwin.forecasting.training import basicts_train as bt
    spec = ModelRegistry.metr_la_gwnet()
    raw, _ = bt._prepared(spec.dataset)
    if raw.shape[1] != spec.graph_size:
        raise RuntimeError("METR-LA sensor count does not match the checkpoint")
    points = {r["node_index"]: [r["lat"], r["lon"]] for r in mapping()["records"]}
    meta = {"name": "METR-LA", "steps": raw.shape[0], "interval_s": 300,
            "first_utc": "2012-03-01T00:00:00", "quantity": "speed mph",
            "nodes": [f"S{i}" for i in range(spec.graph_size)],
            "coords": [points.get(i) for i in range(spec.graph_size)]}
    return meta, np.asarray(raw[:, :, 0], dtype="float64")


def forecast(as_of: int, model: str | None = None):
    model = model or "GWNet"
    if model in {"auto", "automatic"}:
        model = "GWNet"
    if model not in {"GWNet", "persistence"}:
        raise ValueError("Scientific METR-LA supports GWNet and persistence only")
    with _LOCK:
        service = ForecastService.metr_la_gwnet()
        if isinstance(as_of, bool) or not isinstance(as_of, (int, np.integer)) or not 12 <= as_of <= len(service.values):
            raise ValueError(f"as_of must be an integer in [12, {len(service.values)}]")
        if model == "GWNet":
            out = service.predict(as_of)
        else:
            now = service.values[as_of - 1]
            pred = np.repeat(now[None, :], 12, axis=0)
            window = np.asarray(service.raw[as_of - 12:as_of], dtype="float32")
            sha = lambda a: hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]
            out = {"now": now, "prediction": pred, "input_window_hash": sha(window),
                   "raw_prediction_hash": sha(pred), "inference_runtime_s": None,
                   "checkpoint_sha256": None, "nonfinite_values_replaced": 0}
        contract = service.spec.public()
        info = {"resolved_model": model, "checkpoint_path": contract["checkpoint_path"] if model == "GWNet" else None,
                "checkpoint_sha256": out["checkpoint_sha256"], "as_of_index": as_of,
                "inference_seconds": out["inference_runtime_s"], "input_window_hash": out["input_window_hash"],
                "raw_prediction_hash": out["raw_prediction_hash"], "prediction_cache_hit": False,
                "inference_recomputed": True, "result_source": "FRESH_INFERENCE" if model == "GWNet" else "COMPUTED_BASELINE",
                "trust": "FROZEN_SCENARIO_ONLY", "forecast_contract": contract if model == "GWNet" else None,
                "nonfinite_values_replaced": out["nonfinite_values_replaced"],
                "data_scope": "PUBLIC_BENCHMARK_ONLY", "input_scope": "RECORDED_METR_LA"}
        return out["now"], out["prediction"], info


def registry(scope: str) -> dict:
    spec = ModelRegistry.metr_la_gwnet().public()
    valid = spec["validation_status"] == "FORECAST_VALIDATED"
    available = Path(spec["checkpoint_path"]).is_file()
    entry = {"model": "GWNet", "label": "Graph WaveNet", "family": "trained", "trained": True,
             "eligible": False, "can_forecast": available, "status": "VALIDATED" if valid else "NOT_VALIDATED",
             "trust": "FROZEN_SCENARIO_ONLY", "checkpoint_path": spec["checkpoint_path"],
             "test_skill": spec["skill_vs_persistence"].get("+30"),
             "reason": "METR-LA benchmark validation; routing evidence is limited to frozen Scenario A"}
    baseline = {"model": "persistence", "label": "Persistence", "family": "baseline", "trained": False,
                "eligible": False, "can_forecast": True, "status": "BASELINE", "test_skill": 0,
                "reason": "Repeat the final observation; no learned checkpoint"}
    return {"scope": scope, "automatic": "GWNet", "forecast": {"model": "GWNet"},
            "routing": {"eligible": False, "scope": "FROZEN_SCENARIO_ONLY"}, "forecast_contract": spec,
            "groups": [{"key": "validated", "items": [entry]}, {"key": "baselines", "items": [baseline]}]}


def sensor_result(payload: dict, run_id: str) -> dict:
    """Adapt the same whole-graph inference to the existing single-sensor job response."""
    meta, values = series()
    region = payload.get("region", 0)
    if isinstance(region, bool) or not isinstance(region, int) or not 0 <= region < values.shape[1]:
        raise ValueError("region must be a sensor index in the registered graph")
    requested = payload.get("as_of")
    as_of = len(values) if requested in (None, "", "latest") else requested
    now, pred, info = forecast(as_of, payload.get("model"))
    as_of = info["as_of_index"]
    def clean(row):
        return [float(v) if np.isfinite(v) and v > 0 else None for v in row]
    actual = clean(values[as_of:as_of + 12, region]) or None
    prediction = clean(pred[:, region])
    history_start = max(0, as_of - 72)
    clock = lambda i: (datetime.fromisoformat(meta["first_utc"]) + timedelta(seconds=i * 300)).isoformat()
    metrics = {}
    for h in (5, 15, 30, 60):
        k = h // 5 - 1
        observed = actual[k] if actual and k < len(actual) else None
        value = prediction[k]
        metrics[h] = {"predicted": value, "actual": observed,
                      "abs_error": abs(value - observed) if value is not None and observed is not None else None,
                      "persistence_abs_error": abs(float(now[region]) - observed) if observed is not None and now[region] > 0 else None}
    from traffictwin.data.provenance import Run
    record = Run(run_id, dataset="METR-LA", resolved_model=info["resolved_model"],
                 **{k: info[k] for k in ("checkpoint_sha256", "input_window_hash", "raw_prediction_hash", "inference_recomputed", "result_source")})
    record.finish("done")
    return {"run_id": run_id, "dataset": "METR_LA", "model": info["resolved_model"], "region": region,
            "nodes_in_subgraph": values.shape[1], "series_length": len(values),
            "as_of_index": as_of, "as_of_utc": clock(as_of), "quantity": "speed mph",
            "reality": "PUBLIC_BENCHMARK_ONLY", "interval_s": 300,
            "history": clean(values[history_start:as_of, region]), "history_from_utc": clock(history_start),
            "actual": actual, "prediction": prediction, "metrics": metrics,
            "provenance": info, "forecast_contract": info["forecast_contract"],
            "result_source": info["result_source"], "inference_recomputed": True}
