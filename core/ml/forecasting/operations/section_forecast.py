"""A speed forecast for single road sections, from each section's own recent real readings.

Each section is one ordinary time series, so the model needs no road graph and nothing is trained: the released
Chronos-2 weights are used as they are, through the adapter the project already has. A section gets a forecast only
when it has MIN_READINGS consecutive 5-minute readings ending now; a series with a gap is not forecast, because closing
the gap would invent the missing readings. The uncertainty returned is the model's own 10 % and 90 % quantiles. It
has not been checked against later observations (that needs 200 forecast and observation pairs) and is labelled so.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.common import tag
from core.ml.forecasting.adapters.base import CityData, NotAvailable

MIN_READINGS = 8              # the adapter's own minimum (chronos_adapter.MIN_CONTEXT)
HORIZONS_MIN = [15, 30, 60]
BIN_MIN = 5
UNCERTAINTY = "the model's own 10 % to 90 % range, not checked against observations (uncalibrated)"


def unbroken_tail(series: list[dict], bin_min: int = BIN_MIN) -> list[float]:
    """The speeds of the longest run of consecutive bins that ends with the last reading."""
    tail = [series[-1]] if series else []
    for prev in reversed(series[:-1]):
        if datetime.fromisoformat(tail[0]["bin_start"]) - datetime.fromisoformat(prev["bin_start"]) != timedelta(minutes=bin_min):
            break
        tail.insert(0, prev)
    return [r["kmh"] for r in tail]


def default_adapter():
    from core.ml.forecasting.adapters.chronos_adapter import Chronos2Adapter
    return Chronos2Adapter()


def forecast(city_id: str, readings: dict, based_on: str, adapter=None, horizons: list[int] = HORIZONS_MIN) -> tuple[dict, str | None]:
    """({section id: {horizon: tagged speed with its range}}, the reason there is no forecast or None)."""
    import numpy as np
    usable = {sid: tail for sid, r in readings.items() if len(tail := unbroken_tail(r["series"])) >= MIN_READINGS}
    if not usable:
        return {}, "too_few_readings"
    ids = sorted(usable)
    length = min(len(usable[i]) for i in ids)
    data = CityData(city_id=city_id, node_ids=ids, values=np.array([[usable[i][-length:][t] for i in ids] for t in range(length)], dtype="float32"),
                    interval_s=BIN_MIN * 60, unit="km/h")
    try:
        f = (adapter or default_adapter()).forecast(data, horizons)
    except NotAvailable:
        return {}, "model_unavailable"
    except Exception:                                   # noqa: BLE001 - a model that cannot load gives no forecast, not a guess
        return {}, "model_unavailable"
    issued = datetime.now(timezone.utc).isoformat()
    lo, hi = f.provenance.get("lower_q10", {}), f.provenance.get("upper_q90", {})
    out: dict = {}
    for n, sid in enumerate(ids):
        for h in horizons:
            v = f.values[h][n]
            if v != v:
                continue
            t = tag.forecast(f.model, issued, based_on, UNCERTAINTY, horizon_min=h, readings_used=length)
            out.setdefault(sid, {})[str(h)] = tag.tagged(round(max(0.0, v), 1), "km/h", t, range=[round(max(0.0, lo[h][n]), 1), round(max(0.0, hi[h][n]), 1)])
    return out, None
