"""The recorded backtest scores a model and persistence on the same pairs and never fills a gap."""
import numpy as np

from core.ml.forecasting.adapters.base import Forecast
from core.ml.forecasting.evaluation.recorded_backtest import backtest, unbroken_context


class _Last:
    """Forecasts the last reading it was given, so it must score exactly as persistence does."""
    name = "last"

    def forecast(self, data, horizons):
        v = np.asarray(data.values)
        last = [float(c[np.isfinite(c)][-1]) if np.isfinite(c).any() else float("nan") for c in v.T]
        return Forecast(model=self.name, checkpoint="-", dataset_schema="-", input_window_steps=len(v), output_horizon_steps=12,
                        horizons_min=list(horizons), values={h: last for h in horizons}, unit=data.unit, node_ids=data.node_ids,
                        inference_utc="-", city_id=data.city_id, is_baseline=True, provenance={})


def test_context_keeps_only_the_unbroken_run():
    v = np.array([[1.0, 1.0], [np.nan, 2.0], [3.0, 3.0], [4.0, np.nan]])
    ctx = unbroken_context(v, 3)
    assert np.isnan(ctx[:2, 0]).all() and list(ctx[2:, 0]) == [3.0, 4.0]
    assert np.isnan(ctx[:, 1]).all()                      # no reading at the origin: nothing to forecast from


def test_same_pairs_and_no_filled_gap():
    rng = np.random.default_rng(0)
    v = rng.uniform(20, 60, size=(60, 2))
    v[30, 0] = np.nan                                     # a gap: origins need 8 readings in a row again after it
    v[45, 1] = np.nan                                     # a missing target is not scored
    out = backtest(v, list(range(7, 59)), _Last(), "anywhere", "km/h", horizons=[15])["15"]
    assert out["mae_model"] == out["mae_persistence"] and out["skill_vs_persistence"] == 0.0
    scored = sum(1 for t in range(7, 57) for n in (0, 1)
                 if np.isfinite(v[t - 7: t + 1, n]).all() and np.isfinite(v[t + 3, n]))
    assert out["pairs"] == scored


def test_too_short_a_history_scores_nothing():
    v = np.full((20, 1), 30.0)
    assert backtest(v, [3, 4], _Last(), "anywhere", "km/h", horizons=[15])["15"]["pairs"] == 0
