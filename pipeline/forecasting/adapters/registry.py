"""Which models exist, and which of them can honestly serve a given city.

    from pipeline.forecasting.adapters.registry import available_for, forecast

`available_for(city_data)` returns every adapter with its gate result, so an interface can show a
user *why* a model is unavailable instead of silently offering fewer options. `forecast()` picks
the best model that passes, and falls back to a labelled BASELINE rather than to nothing — but it
never lets a baseline be presented as the system's forecast.
"""
from __future__ import annotations

from .base import CityData, Forecast, ForecastAdapter, NotAvailable
from .baselines import HistoricalAverageAdapter, PersistenceAdapter
from .checkpoint_models import GraphWaveNetAdapter, STAEformerAdapter, STIDAdapter
from .chronos_adapter import ChronosAdapter
from .opencity import OpenCityAdapter

# Strongest first: a foundation model that transfers, then city-specific networks, then floors.
def all_adapters(dataset_hint: str | None = None) -> list[ForecastAdapter]:
    ds = dataset_hint or "METR-LA"
    # Strongest-and-applicable first. Chronos sits above the baselines because it is a real
    # pretrained model that serves cities the graph models must refuse, and below them because it
    # cannot see the road network.
    return [OpenCityAdapter(),
            STAEformerAdapter(ds), GraphWaveNetAdapter(ds), STIDAdapter(ds),
            ChronosAdapter(),
            HistoricalAverageAdapter(), PersistenceAdapter()]


def available_for(city_data: CityData, dataset_hint: str | None = None) -> list[dict]:
    out = []
    for ad in all_adapters(dataset_hint):
        try:
            chk = ad.check(city_data)
        except Exception as exc:                     # noqa: BLE001 - reported, never hidden
            chk = {"ok": False, "reasons": [f"{type(exc).__name__}: {exc}"]}
        out.append({**ad.describe(), "available": bool(chk.get("ok")),
                    "reasons": chk.get("reasons", []), "gates": chk.get("gates")})
    return out


def forecast(city_data: CityData, horizons_min: list[int],
             model: str | None = None, dataset_hint: str | None = None) -> dict:
    """Return the forecast plus the full menu, so the caller can see what was NOT used and why."""
    menu = available_for(city_data, dataset_hint)
    chosen, result, errors = None, None, []
    for ad in all_adapters(dataset_hint):
        if model and ad.name != model:
            continue
        try:
            result = ad.forecast(city_data, horizons_min)
            chosen = ad
            break
        except NotAvailable as exc:
            errors.append({"model": ad.name, "reasons": exc.reasons})
        except Exception as exc:                     # noqa: BLE001
            errors.append({"model": ad.name, "reasons": [f"{type(exc).__name__}: {exc}"]})
    return {
        "forecast": result.to_dict() if result else None,
        "model_used": chosen.name if chosen else None,
        "is_baseline": bool(result.is_baseline) if result else None,
        "models": menu,
        "refusals": errors,
        "note": ("A baseline is labelled as one. If every real model refused, the reasons are in "
                 "`refusals` — the system does not present a floor as a forecast."),
    }
