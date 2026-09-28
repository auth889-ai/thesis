"""The one forecasting contract used by the canonical closed-loop experiment.

The service intentionally exposes a narrow, inspectable contract.  It does not turn a benchmark
checkpoint into a city claim: METR-LA is the only canonical DL scope until another dataset passes
its own chronological held-out trust gate.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO

VERIFY = REPO / "results/forecasting/verify_GWNet_METR-LA_207.json"


@dataclass(frozen=True)
class ModelSpec:
    model: str
    dataset: str
    checkpoint_path: str
    checkpoint_sha256: str
    graph_size: int
    input_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    horizons_min: tuple[int, ...]
    parameters: dict
    metrics: dict
    skill_vs_persistence: dict
    validation_status: str
    data_scope: str

    def public(self) -> dict:
        return {"model": self.model, "dataset": self.dataset, "checkpoint_path": self.checkpoint_path,
                "checkpoint_sha256": self.checkpoint_sha256, "parameters": self.parameters,
                "input_shape": list(self.input_shape), "output_shape": list(self.output_shape),
                "graph_size": self.graph_size, "horizons_min": list(self.horizons_min),
                "metrics": self.metrics, "skill_vs_persistence": self.skill_vs_persistence,
                "validation_status": self.validation_status, "data_scope": self.data_scope}


class ModelRegistry:
    """Evidence-backed model registry for the scientific core.

    The dashboard's older registry is retained as a compatibility adapter for uploads and live
    prototypes.  This registry is the sole authority for canonical closed-loop experiments.
    """

    @staticmethod
    def metr_la_gwnet() -> ModelSpec:
        evidence = json.loads(VERIFY.read_text())
        held_out = evidence["held_out"]
        skill = {h: values["skill"] for h, values in held_out.items()}
        metrics = {h: {"MAE": values["MAE"],
                       "RMSE": evidence["logged_test_metrics"][f"horizon_{int(h[1:]) // 5}"]["RMSE"]}
                   for h, values in held_out.items()}
        valid = all(value > 0 for value in skill.values())
        return ModelSpec(
            model="GWNet",
            dataset="METR-LA",
            checkpoint_path=evidence["checkpoint"],
            checkpoint_sha256=evidence["checkpoint_sha256"],
            graph_size=int(evidence["nodes"]),
            input_shape=(1, 12, int(evidence["nodes"]), 1),
            output_shape=(1, 12, int(evidence["nodes"]), 1),
            horizons_min=(15, 30, 60),
            parameters={"architecture": "GraphWaveNet", "history_steps": 12, "forecast_steps": 12,
                        "signal": "speed_mph", "upstream_harness": "BasicTS-legacy"},
            metrics=metrics,
            skill_vs_persistence=skill,
            validation_status="FORECAST_VALIDATED" if valid else "FORECAST_NOT_VALIDATED",
            data_scope="PUBLIC_BENCHMARK_ONLY",
        )


class ForecastService:
    """Fresh Graph WaveNet inference plus the immutable contract attached to every output."""

    def __init__(self, spec: ModelSpec):
        self.spec = spec
        from traffictwin.forecasting.training import basicts_train as bt

        self._bt = bt
        self.raw, _ = bt._prepared(spec.dataset)
        self.values = np.asarray(self.raw[:, :, 0], dtype="float64")
        self.card = {"arch": "GWNet", "arch_class": "GraphWaveNet", "bts_name": spec.dataset,
                     "checkpoint": spec.checkpoint_path}

    @classmethod
    def metr_la_gwnet(cls) -> "ForecastService":
        return cls(ModelRegistry.metr_la_gwnet())

    def predict(self, as_of: int, *, include_tensor_hash=False) -> dict:
        """Run a fresh forward pass using exactly the twelve observations before ``as_of``."""
        if isinstance(as_of, bool) or not isinstance(as_of, (int, np.integer)) or not 12 <= as_of <= self.raw.shape[0]:
            raise ValueError(f"as_of must be an integer in [12, {self.raw.shape[0]}]")
        checkpoint_sha = hashlib.sha256(Path(self.spec.checkpoint_path).read_bytes()).hexdigest()
        if not checkpoint_sha.startswith(self.spec.checkpoint_sha256):
            raise RuntimeError("checkpoint does not match the validated ModelRegistry record")
        start = time.perf_counter()
        tensor_hash = None
        if include_tensor_hash:
            prediction, tensor_hash = self._bt.predict(self.card, as_of, return_input_hash=True)
        else:
            prediction = self._bt.predict(self.card, as_of)
        runtime_s = round(time.perf_counter() - start, 3)
        if prediction.shape != (12, self.spec.graph_size):
            raise RuntimeError("forecast shape does not match the registered graph")
        replaced = int((~np.isfinite(prediction)).sum())
        prediction = np.where(np.isfinite(prediction), prediction, self.values[as_of - 1][None, :])
        input_window = np.asarray(self.raw[as_of - 12:as_of], dtype="float32")
        sha = lambda a: hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]
        return {"prediction": prediction, "now": self.values[as_of - 1], "as_of": as_of,
                "inference_runtime_s": runtime_s, "input_window_hash": sha(input_window),
                "raw_prediction_hash": sha(prediction), "contract": self.spec.public(),
                "checkpoint_sha256": checkpoint_sha, "inference_recomputed": True,
                "nonfinite_values_replaced": replaced, "input_tensor_sha256": tensor_hash}
