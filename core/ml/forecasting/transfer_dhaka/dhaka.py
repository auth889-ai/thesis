"""RQ1 on Dhaka's recorded days (DhaTraX v1.0, CC BY 4.0): one recorded day per camera site, 5-minute median speed in km/h.
Rolling origin over each day with a one-hour context (12 readings), horizons 15/30/60 minutes. Persistence and the three
foundation models through Protocol B's own prediction functions, so Dhaka is forecast by exactly the same code as METR-LA.
No historical average: a site has a single recorded day, so there is no other day to average (said, not guessed).
The models are deterministic, so there are no seeds; the spread is over sites."""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.evaluation.recorded_backtest import dhatrax_site
from core.ml.forecasting.transfer_dhaka.metrics import BIN_MIN, HORIZONS_MIN, score

CONTEXT = 12                                                         # one hour of 5-minute readings
STEPS = max(HORIZONS_MIN) // BIN_MIN


def windows(values: np.ndarray, context: int = CONTEXT, steps: int = STEPS) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ctx (W, context, 1), truth (W, steps, 1), origins). Missing readings become 0.0 (an outage, as in METR-LA): a context
    with a gap still forecasts, a missing target is not scored. Only origins with a full context and a full horizon are used."""
    v = np.nan_to_num(values.astype("float32"), nan=0.0)
    origins = [t for t in range(context - 1, len(v) - steps) if (v[t - context + 1:t + 1, 0] > 0).all()]
    ctx = np.stack([v[t - context + 1:t + 1] for t in origins]) if origins else np.zeros((0, context, 1), "float32")
    truth = np.stack([v[t + 1:t + 1 + steps] for t in origins]) if origins else np.zeros((0, steps, 1), "float32")
    return ctx, truth, np.array(origins)


def persistence(ctx: np.ndarray, steps: int = STEPS) -> np.ndarray:
    return np.repeat(ctx[:, -1:, :], steps, axis=1)


def evaluate_site(site: dict, models: dict) -> dict:
    """`models`: name -> fn(ctx, steps) -> (W, steps, 1)."""
    values, _, meta = dhatrax_site(site)
    ctx, truth, origins = windows(values)
    preds = {"persistence": persistence(ctx)} | {name: fn(ctx, STEPS) for name, fn in models.items()}
    return {"site": site["site"], "day": site.get("day"), "windows": int(len(origins)), "context_steps": CONTEXT, "unit": "km/h",
            "results": {name: score(p, truth) for name, p in preds.items()}, "meta": {k: meta[k] for k in ("dataset", "series", "limits")}}
