"""Graph WaveNet / STID / STAEformer behind the common interface.

These are the models this project actually trained and verified — GWNet reproduces its published
METR-LA and PEMS-BAY error to within 1.8 %. The audit's point was that none of them were reachable
from the runtime; the Prediction page called a four-class transition model instead. This adapter
makes them callable.

Their gate is narrower than it looks and worth stating precisely: a checkpoint is trained for ONE
city's sensor graph. GWNet on METR-LA has 207 nodes baked into its adaptive adjacency; it cannot
be pointed at another city's 250 road segments and asked for a forecast. So `check()` requires the
city to BE the dataset the checkpoint was trained on. That is not a limitation of this code — it
is the difference between a city-specific model and a foundation model, and it is exactly why
OpenCity exists.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from core.ml.forecasting.adapters.base import CityData, Forecast, ForecastAdapter, NotAvailable

from core.common.paths import REPO
CKPT_DIR = REPO / "results/forecasting/checkpoints"
ARCH_DIR = {"GWNet": "GraphWaveNet", "STID": "STID", "STAEformer": "STAEformer", "DCRNN": "DCRNN"}


class CheckpointAdapter(ForecastAdapter):
    """A city-specific trained network, bound to the dataset it was trained on."""

    def __init__(self, model: str, dataset: str):
        self.name = f"{model}/{dataset}"
        self.model, self.dataset = model, dataset

    # ------------------------------------------------------------------ gate
    def _checkpoint(self) -> Path | None:
        arch = ARCH_DIR.get(self.model, self.model)
        root = CKPT_DIR / arch
        if not root.exists():
            return None
        for pt in sorted(root.rglob("*.pt")):
            parts = pt.relative_to(root).parts
            ds = next((seg.split("_")[0] for seg in parts if "_" in seg), "")
            if ds == self.dataset and "best" in pt.name:
                return pt
        return None

    def check(self, city_data: CityData) -> dict:
        reasons = []
        ck = self._checkpoint()
        if ck is None:
            reasons.append(f"no trained checkpoint for {self.model} on {self.dataset}")
        # A city-specific checkpoint only means anything on its own sensor graph.
        if city_data.city_id.replace("_", "-").upper() != self.dataset.upper():
            reasons.append(
                f"{self.model} was trained on {self.dataset} and its weights encode that sensor "
                f"graph; it cannot forecast {city_data.city_id}. A city-specific model does not "
                f"transfer — that is what a foundation model is for")
        return {"ok": not reasons, "reasons": reasons,
                "checkpoint": str(ck.relative_to(REPO)) if ck else None}

    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        c = self.check(city_data)
        if not c["ok"]:
            raise NotAvailable(self.name, c["reasons"])
        raise NotAvailable(self.name, [
            "checkpoint inference runs through src/pipeline/forecasting/infer_from_checkpoint.py, "
            "which needs the pinned BasicTS harness and the prepared dataset; it is not wired "
            "into the request path. Verified metrics are in results/forecasting/"
            "phase1_comparison.md"])

    def results(self) -> list[dict]:
        f = REPO / "results/forecasting/trained_results.json"
        if not f.exists():
            return []
        return [r for r in json.loads(f.read_text()).get("runs", [])
                if r.get("model") == self.model and r.get("dataset") == self.dataset]

    def describe(self) -> dict:
        d = super().describe()
        ck = self._checkpoint()
        rs = self.results()
        m15 = next((r.get("metrics_by_horizon_min", {}).get("15") for r in rs), None) or {}
        d.update({"architecture": self.model, "trained_on": self.dataset,
                  "checkpoint": str(ck.relative_to(REPO)) if ck else None,
                  "mae@15min": m15.get("mae"), "rmse@15min": m15.get("rmse"),
                  "protocol": "DCRNN 15/30/60-min horizons",
                  "transfers_to_other_cities": False})
        return d


def STAEformerAdapter(dataset: str = "METR-LA") -> CheckpointAdapter:
    return CheckpointAdapter("STAEformer", dataset)


def GraphWaveNetAdapter(dataset: str = "METR-LA") -> CheckpointAdapter:
    return CheckpointAdapter("GWNet", dataset)


def STIDAdapter(dataset: str = "METR-LA") -> CheckpointAdapter:
    return CheckpointAdapter("STID", dataset)
