"""OpenCity behind the common interface — and refusing cities it cannot honestly serve.

The reproduction is done and stands: PEMS07M and TrafficSH both REPRODUCTION_PASS against the
authors' published Table 1. This adapter is what turns that from a result in a file into a model
the runtime can call.

It is also where the "do not falsely run OpenCity on arbitrary live cities" rule is enforced. The
gates are the model's own: a 288-step input window, a graph in the range its pre-training corpus
covers, and — the one that is easy to forget — the city must be ABSENT from that corpus for the
word zero-shot to be usable at all. `check()` returns every failing gate, and `forecast()` refuses
rather than returning a number that would look identical to a valid one.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .base import CityData, Forecast, ForecastAdapter, NotAvailable

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream"))
CKPT = WORKSPACE / "OpenCity/model_weights/OpenCity/OpenCity-plus.pth"
CKPT_SHA = "ae4235615a914c831543275642152409075e1a3f07d564a27fab28364d59af7b"

HIS = PRED = 288
MIN_NODES = 20


class OpenCityAdapter(ForecastAdapter):
    name = "OpenCity-plus"

    def __init__(self, pretraining_corpus: set[str] | None = None):
        from pipeline.city.datasets import OPENCITY_PRETRAINING
        self.corpus = pretraining_corpus or OPENCITY_PRETRAINING

    def check(self, city_data: CityData) -> dict:
        reasons = []
        if not CKPT.exists():
            reasons.append(f"released checkpoint not present at {CKPT}")
        T, N = (city_data.shape + (0, 0))[:2]
        if T < HIS:
            reasons.append(f"input window needs {HIS} steps, this city has {T}")
        if N < MIN_NODES:
            reasons.append(f"graph has {N} nodes; the pre-training corpus holds hundreds")
        if city_data.city_id in self.corpus:
            reasons.append(f"{city_data.city_id} is IN OpenCity's pre-training corpus — a result "
                           f"here cannot be called zero-shot")
        return {"ok": not reasons, "reasons": reasons,
                "gates": {"input_window_steps": HIS, "min_nodes": MIN_NODES,
                          "must_be_outside_pretraining_corpus": True}}

    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        c = self.check(city_data)
        if not c["ok"]:
            raise NotAvailable(self.name, c["reasons"])
        raise NotAvailable(self.name, [
            "live inference is not wired: OpenCity-plus needs its adjacency, the authors' config "
            "stack and GPU-sized memory, so it runs as a batch job (aws_train.py --opencity), not "
            "in the request path. Reproduction results are in results/forecasting/"
            "opencity_crosscity.md; this adapter reports capability and refuses to fabricate."])

    def reproduction(self) -> list[dict]:
        """The verified results, so the runtime can show what this model has actually done here."""
        f = REPO / "results/forecasting/opencity_crosscity.json"
        return json.loads(f.read_text()) if f.exists() else []

    def describe(self) -> dict:
        d = super().describe()
        d.update({"checkpoint": CKPT.name if CKPT.exists() else None,
                  "checkpoint_sha256": CKPT_SHA if CKPT.exists() else None,
                  "input_window_steps": HIS, "output_horizon_steps": PRED,
                  "upstream": "HKUDS/OpenCity @ eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f",
                  "weights": "huggingface hkuds/OpenCity-Plus, used as released"})
        return d
