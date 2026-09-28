"""Which models exist, and which of them can honestly serve a given city.

    from app.forecasting.adapters.registry import available_for, forecast

`available_for(city_data)` returns every adapter with its gate result, so an interface can show a
user *why* a model is unavailable instead of silently offering fewer options. `forecast()` picks
the best model that passes, and falls back to a labelled BASELINE rather than to nothing — but it
never lets a baseline be presented as the system's forecast.
"""
from __future__ import annotations

from app.forecasting.adapters.base import CityData, Forecast, ForecastAdapter, NotAvailable
from app.forecasting.adapters.baselines import HistoricalAverageAdapter, PersistenceAdapter
from app.forecasting.adapters.checkpoint_models import GraphWaveNetAdapter, STAEformerAdapter, STIDAdapter
from app.forecasting.adapters.chronos_adapter import ChronosAdapter
from app.forecasting.adapters.opencity import OpenCityAdapter

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


def select(city_data: CityData, requested: str | None = None,
           dataset_hint: str | None = None) -> dict:
    """Decide WHICH model should serve this city, and record why — never silently.

    The rule, stated once here rather than implied by ordering:

        compatible graph history        -> a spatio-temporal model (STAEformer / OpenCity)
        sufficient univariate history   -> Chronos
        neither                         -> a labelled BASELINE, or LIVE_ONLY if even that fails

    A request for a specific model is honoured when that model can serve the data, and REFUSED
    with reasons when it cannot — the caller is never quietly given a different model's answer
    under the name they asked for.
    """
    menu = available_for(city_data, dataset_hint)
    by_name = {m["model"]: m for m in menu}
    eligible = [m for m in menu if m["available"]]

    decision = {
        "requested_model": requested,
        "selected_model": None,
        "reason": None,
        "capability_gate": None,
        "fallback": False,
        "fallback_from": None,
        "rule": ("graph history -> spatio-temporal model; univariate history -> Chronos; "
                 "otherwise a labelled baseline"),
        "candidates": menu,
    }

    if requested:
        m = by_name.get(requested)
        if m is None:
            decision["reason"] = f"{requested!r} is not a registered model"
            return decision
        if not m["available"]:
            decision["reason"] = f"{requested} cannot serve this city: " + "; ".join(m["reasons"])
            decision["capability_gate"] = m.get("gates")
            return decision
        decision.update(selected_model=requested, reason=f"{requested} was requested and can serve this city",
                        capability_gate=m.get("gates"))
        return decision

    spatio = [m for m in eligible if not m.get("is_baseline") and m.get("needs_graph") is not False
              and m["model"] != "Chronos-Bolt"]
    univariate = [m for m in eligible if m["model"] == "Chronos-Bolt"]
    baselines = [m for m in eligible if m.get("is_baseline")]

    if spatio:
        pick = spatio[0]
        decision.update(selected_model=pick["model"], capability_gate=pick.get("gates"),
                        reason="a spatio-temporal model can serve this city's graph history")
    elif univariate:
        pick = univariate[0]
        blocked = [m["model"] for m in menu
                   if not m["available"] and not m.get("is_baseline") and m["model"] != "Chronos-Bolt"]
        decision.update(selected_model=pick["model"], capability_gate=pick.get("gates"),
                        fallback=bool(blocked), fallback_from=blocked,
                        reason=("no spatio-temporal model can serve this city, but there is enough "
                                "univariate history for a pretrained foundation model"))
    elif baselines:
        pick = baselines[0]
        decision.update(selected_model=pick["model"], fallback=True,
                        fallback_from=[m["model"] for m in menu if not m["available"]],
                        reason=("no trained or pretrained model can serve this city; a BASELINE is "
                                "returned and labelled as one"))
    else:
        decision["reason"] = ("no model can serve this city at all — it is LIVE_ONLY until more "
                              "history accumulates")
    return decision


def forecast(city_data: CityData, horizons_min: list[int],
             model: str | None = None, dataset_hint: str | None = None) -> dict:
    """Run the selected model. The decision is returned alongside, never hidden."""
    decision = select(city_data, model, dataset_hint)
    result, errors = None, []
    target = decision["selected_model"]
    if target:
        for ad in all_adapters(dataset_hint):
            if ad.name != target:
                continue
            try:
                result = ad.forecast(city_data, horizons_min)
            except NotAvailable as exc:
                errors.append({"model": ad.name, "reasons": exc.reasons})
            except Exception as exc:                 # noqa: BLE001
                errors.append({"model": ad.name, "reasons": [f"{type(exc).__name__}: {exc}"]})
            break
    for m in decision["candidates"]:
        if not m["available"] and m["reasons"]:
            errors.append({"model": m["model"], "reasons": m["reasons"]})

    return {
        "forecast": result.to_dict() if result else None,
        "model_used": result.model if result else None,
        "is_baseline": bool(result.is_baseline) if result else None,
        "decision": decision,
        "models": decision["candidates"],
        "refusals": errors,
        "note": ("`decision` states which model was selected and why. A baseline is labelled as "
                 "one, and a requested model that cannot serve the data is refused rather than "
                 "silently swapped."),
    }
