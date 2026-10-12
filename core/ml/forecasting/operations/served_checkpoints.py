"""Serve any trained checkpoint on the forecast map: the official architecture reloaded once from its
best-validation checkpoint (the same loader Protocol B uses), a fresh forward pass per request on the twelve
observations before `as_of`, the checkpoint's SHA-256 and its leaderboard row attached to every answer."""
from __future__ import annotations

import hashlib
import json
import threading
import time

import numpy as np

from core.ml.forecasting.evaluation.checkpoint_stage import ARCH, _load_model, checkpoints_for, harness_array
from core.common.paths import REPO

IN_LEN = 12
_LOCK = threading.Lock()
_LOADED: dict[tuple[str, str], tuple] = {}
RESULTS = REPO / "results/forecasting/trained_results.json"


def available(dataset: str = "METR-LA") -> dict[str, dict]:
    """{model name: checkpoint record} for every architecture with a best-validation checkpoint on this dataset."""
    out = {}
    for ck in checkpoints_for(dataset):
        name = ARCH[ck["arch"]]
        out[name] = {"model": name, "arch": ck["arch"], "checkpoint_path": str(ck["path"].relative_to(REPO)),
                     "checkpoint_sha256": hashlib.sha256(ck["path"].read_bytes()).hexdigest(), "dataset": dataset}
    return out


def leaderboard_row(model: str, dataset: str = "METR-LA") -> dict | None:
    if not RESULTS.exists():
        return None
    for r in json.loads(RESULTS.read_text()).get("runs", []):
        if r["model"] == model and r["dataset"] == dataset:
            return {"metrics_by_horizon_min": r.get("metrics_by_horizon_min"), "published": r.get("published"), "log": r.get("log")}
    return None


def _model(model: str, dataset: str, raw):
    key = (model, dataset)
    if key not in _LOADED:
        ck = {ARCH[c["arch"]]: c for c in checkpoints_for(dataset)}[model]
        probe = np.array(raw[0:IN_LEN], dtype="float32")[None]
        _LOADED[key] = (*_load_model(ck["arch"], dataset, ck["path"], probe), hashlib.sha256(ck["path"].read_bytes()).hexdigest(), str(ck["path"].relative_to(REPO)))
    return _LOADED[key]


def forecast(model: str, as_of: int, dataset: str = "METR-LA") -> dict:
    """Fresh inference: {"now", "prediction" (12, N) in the data's units, hashes, runtime, checkpoint}."""
    import torch
    with _LOCK:
        raw = harness_array(dataset)
        T = raw.shape[0]
        if isinstance(as_of, bool) or not isinstance(as_of, (int, np.integer)) or not IN_LEN <= as_of <= T:
            raise ValueError(f"as_of must be an integer in [{IN_LEN}, {T}]")
        net, fwd, L, H, sha, path = _model(model, dataset, raw)
        n_train = int(T * 0.7)
        mu, sd = float(raw[:n_train, :, 0].mean()), float(raw[:n_train, :, 0].std())
        x = np.array(raw[as_of - L:as_of], dtype="float32")[None]
        x[..., 0] = (x[..., 0] - mu) / sd
        f = np.array(raw[as_of:as_of + H], dtype="float32")[None] if as_of + H <= T else np.zeros((1, H, raw.shape[1], raw.shape[2]), dtype="float32")
        f[..., 0] = 0.0                                          # known covariates only; never the future speed
        t0 = time.perf_counter()
        with torch.no_grad():
            o = net(history_data=torch.tensor(x)[..., fwd], future_data=torch.tensor(f), batch_seen=0, epoch=1, train=False)
        pred = (o if isinstance(o, torch.Tensor) else o["prediction"]).numpy()[0, ..., 0] * sd + mu
        runtime = round(time.perf_counter() - t0, 3)
        now = np.asarray(raw[as_of - 1, :, 0], dtype="float64")
        replaced = int((~np.isfinite(pred)).sum())
        pred = np.where(np.isfinite(pred), pred, now[None, :])
        h = lambda a: hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]
        return {"now": now, "prediction": pred[:12], "inference_runtime_s": runtime, "input_window_hash": h(x),
                "raw_prediction_hash": h(pred), "checkpoint_sha256": sha, "checkpoint_path": path,
                "nonfinite_values_replaced": replaced, "leaderboard": leaderboard_row(model, dataset)}
