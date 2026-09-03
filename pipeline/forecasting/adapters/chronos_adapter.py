"""Chronos — a pretrained time-series foundation model that Dhaka can actually use today.

WHY THIS ONE MATTERS HERE
    Every spatio-temporal model in this project needs a graph: OpenCity wants hundreds of nodes and
    288 steps of history, Graph WaveNet bakes a specific sensor adjacency into its weights. Dhaka
    has twelve corridors and no sensor network, so all of them correctly refuse it.

    Chronos is a different shape of model. It is UNIVARIATE: each series is forecast on its own,
    with no adjacency, no node-count minimum and a short context. Twelve corridors is not a
    deficient graph to Chronos — it is twelve perfectly ordinary series. So the city that no
    spatio-temporal model can serve is served by this one, zero-shot, with uncertainty bands.

    That is the honest answer to "our data is too small": it was too small for one FAMILY of model.

WHAT IS GIVEN UP, AND IT IS NOT NOTHING
    Chronos cannot see the road network. It has no way to know that a jam on one corridor predicts
    a jam on the next, which is the entire premise of the graph models and the reason they win on
    METR-LA. Expect it to be beaten by a properly-trained spatio-temporal model wherever one can be
    trained. Its value is coverage, not peak accuracy.

EXPOSURE, STATED RATHER THAN ASSUMED
    Chronos was pre-trained on a large public corpus that includes traffic data. Whether any
    specific benchmark here was inside it has NOT been verified, so `pretraining_exposure` reports
    "UNVERIFIED" rather than claiming a clean zero-shot result on METR-LA or PEMS-BAY. The same
    discipline that disqualified those cities for OpenCity applies here.

Upstream: amazon-science/chronos-forecasting (Apache-2.0), weights from HuggingFace as released.
"""
from __future__ import annotations

import numpy as np

from .base import CityData, Forecast, ForecastAdapter, NotAvailable

DEFAULT_MODEL = "amazon/chronos-bolt-small"
MIN_CONTEXT = 8            # below this a foundation model is guessing from noise
MAX_CONTEXT = 2048
QUANTILES = [0.1, 0.5, 0.9]


class ChronosAdapter(ForecastAdapter):
    name = "Chronos-Bolt"

    def __init__(self, model_id: str = DEFAULT_MODEL, device: str = "cpu"):
        self.model_id = model_id
        self.device = device
        self._pipe = None

    # ------------------------------------------------------------------ gate
    def check(self, city_data: CityData) -> dict:
        reasons = []
        try:
            import chronos  # noqa: F401
        except ImportError:
            reasons.append("chronos-forecasting is not installed (pip install chronos-forecasting)")
        T = city_data.shape[0] if city_data.shape else 0
        if T < MIN_CONTEXT:
            reasons.append(f"needs at least {MIN_CONTEXT} observations, this city has {T}")
        return {"ok": not reasons, "reasons": reasons,
                "gates": {"min_context_steps": MIN_CONTEXT, "needs_graph": False,
                          "needs_node_minimum": False,
                          "why_it_fits_small_cities": (
                              "univariate: each node is forecast independently, so a 12-corridor "
                              "city is twelve ordinary series rather than a deficient graph")}}

    def _pipeline(self):
        if self._pipe is None:
            import torch
            from chronos import BaseChronosPipeline
            self._pipe = BaseChronosPipeline.from_pretrained(
                self.model_id, device_map=self.device, torch_dtype=torch.float32)
        return self._pipe

    # -------------------------------------------------------------- forecast
    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        c = self.check(city_data)
        if not c["ok"]:
            raise NotAvailable(self.name, c["reasons"])
        import torch

        v = np.asarray(city_data.values, dtype="float32")
        if v.ndim == 3:
            v = v[..., 0]
        v = v[-MAX_CONTEXT:]
        step = max(1, city_data.interval_s // 60)
        steps_needed = max(int(np.ceil(h / step)) for h in horizons_min)

        # One series per node. Gaps are carried forward rather than zero-filled: a zero would be
        # read as "stationary traffic", which is a value, not a gap.
        series, usable = [], []
        for n in range(v.shape[1]):
            s = v[:, n]
            finite = s[np.isfinite(s)]
            if len(finite) < MIN_CONTEXT:
                continue
            series.append(torch.tensor(finite))
            usable.append(n)
        if not series:
            raise NotAvailable(self.name, ["no node has enough finite observations"])

        q, _mean = self._pipeline().predict_quantiles(
            series, prediction_length=steps_needed, quantile_levels=QUANTILES)
        q = q.detach().cpu().numpy()               # (n_series, steps, n_quantiles)

        values, lo, hi = {}, {}, {}
        for h in horizons_min:
            k = min(int(np.ceil(h / step)) - 1, steps_needed - 1)
            med = [float("nan")] * v.shape[1]
            l = [float("nan")] * v.shape[1]
            u = [float("nan")] * v.shape[1]
            for i, n in enumerate(usable):
                l[n], med[n], u[n] = (round(float(q[i, k, 0]), 3),
                                      round(float(q[i, k, 1]), 3),
                                      round(float(q[i, k, 2]), 3))
            values[h], lo[h], hi[h] = med, l, u

        return Forecast(
            model=self.name, checkpoint=self.model_id,
            dataset_schema=f"{city_data.city_id}: {len(usable)} univariate series, no graph used",
            input_window_steps=int(v.shape[0]),
            output_horizon_steps=steps_needed, horizons_min=list(horizons_min),
            values=values, unit=city_data.unit, node_ids=city_data.node_ids,
            inference_utc=self._now(), city_id=city_data.city_id, is_baseline=False,
            provenance={
                "upstream": "amazon-science/chronos-forecasting (Apache-2.0)",
                "weights": f"HuggingFace {self.model_id}, used as released",
                "family": "univariate time-series foundation model",
                "uses_road_graph": False,
                "quantiles": QUANTILES, "lower_q10": lo, "upper_q90": hi,
                "nodes_forecast": len(usable), "nodes_total": int(v.shape[1]),
                "pretraining_exposure": "UNVERIFIED",
                "exposure_note": (
                    "Chronos was pre-trained on a large public corpus that includes traffic data. "
                    "Whether any benchmark used here was inside it has not been verified, so no "
                    "zero-shot claim is made on METR-LA or PEMS-BAY"),
                "limitation": (
                    "no spatial awareness: it cannot use the road graph, so a properly trained "
                    "spatio-temporal model should beat it wherever one can be trained"),
            })

    def describe(self) -> dict:
        d = super().describe()
        d.update({"checkpoint": self.model_id, "family": "univariate foundation model",
                  "needs_graph": False, "min_context_steps": MIN_CONTEXT,
                  "upstream": "amazon-science/chronos-forecasting",
                  "why_available_here": "works on any city, however few nodes it has"})
        return d
