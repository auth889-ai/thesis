"""Arithmetic baselines — explicitly labelled as baselines, never as the main prediction.

The audit's demand was to demote the empirical transition model. It is kept, because a floor any
model must beat is worth having, but it now sits behind the same interface as the real models with
`is_baseline = True`, so an interface can never present it as the system's forecast.

Persistence is included for the same reason it is in every forecasting paper: on sticky signals it
is embarrassingly hard to beat, and a model that cannot beat it has not earned its complexity.
"""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.adapters.base import CityData, Forecast, ForecastAdapter, NotAvailable


class PersistenceAdapter(ForecastAdapter):
    """The last observed value, held flat. The floor."""

    name = "persistence"
    is_baseline = True

    def check(self, city_data: CityData) -> dict:
        T = city_data.shape[0] if city_data.shape else 0
        return {"ok": T >= 1, "reasons": [] if T >= 1 else ["no observations yet"]}

    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        c = self.check(city_data)
        if not c["ok"]:
            raise NotAvailable(self.name, c["reasons"])
        v = np.asarray(city_data.values, dtype="float32")
        if v.ndim == 3:
            v = v[..., 0]
        last = v[-1]
        return Forecast(
            model=self.name, checkpoint=None,
            dataset_schema=f"{city_data.city_id}: T x N over stable nodes",
            input_window_steps=1, output_horizon_steps=max(horizons_min) * 60 // city_data.interval_s,
            horizons_min=list(horizons_min),
            values={h: [round(float(x), 3) for x in last] for h in horizons_min},
            unit=city_data.unit, node_ids=city_data.node_ids, inference_utc=self._now(),
            city_id=city_data.city_id, is_baseline=True,
            provenance={"method": "last observed value, held flat",
                        "why_reported": "the floor any trained model must beat"})


class HistoricalAverageAdapter(ForecastAdapter):
    """Mean per node over the observed history. The second floor."""

    name = "historical_average"
    is_baseline = True

    def check(self, city_data: CityData) -> dict:
        T = city_data.shape[0] if city_data.shape else 0
        return {"ok": T >= 2, "reasons": [] if T >= 2 else [f"needs >= 2 observations, has {T}"]}

    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        c = self.check(city_data)
        if not c["ok"]:
            raise NotAvailable(self.name, c["reasons"])
        v = np.asarray(city_data.values, dtype="float32")
        if v.ndim == 3:
            v = v[..., 0]
        with np.errstate(invalid="ignore"):
            mean = np.nanmean(v, axis=0)
        return Forecast(
            model=self.name, checkpoint=None,
            dataset_schema=f"{city_data.city_id}: T x N over stable nodes",
            input_window_steps=int(v.shape[0]),
            output_horizon_steps=max(horizons_min) * 60 // city_data.interval_s,
            horizons_min=list(horizons_min),
            values={h: [round(float(x), 3) for x in mean] for h in horizons_min},
            unit=city_data.unit, node_ids=city_data.node_ids, inference_utc=self._now(),
            city_id=city_data.city_id, is_baseline=True,
            provenance={"method": "per-node mean over observed history",
                        "why_reported": "a model below this has learned nothing"})
