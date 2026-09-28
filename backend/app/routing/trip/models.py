"""Which forecast models can serve a city's corridor history right now, with reasons — the
registry's own gates, so the menu never offers a model that would refuse."""
from __future__ import annotations

from .places import city_id_for, is_dhaka


def models_for_city(city: str) -> list[dict]:
    from app.forecasting.adapters.registry import available_for
    from app.data.live_providers import observatory as obs_mod
    cid = city_id_for(city)
    out = [{"model": "auto", "label": "Automatic (best available)", "available": True, "reasons": []}]
    scope = city if str(city).startswith("user:") else cid if str(cid or "").startswith("user:") else None
    if scope:                                          # an uploaded dataset: the registry's own list for that data (trained, pretrained, baselines)
        from app.forecasting.operations import model_registry
        try:
            reg = model_registry.registry(scope)
        except (Exception, SystemExit) as exc:         # noqa: BLE001
            return out + [{"model": "GWNet", "label": "GWNet", "available": False, "reasons": [f"registry unavailable: {exc}"[:200]]}]
        for g in reg.get("groups", []):
            for e in g.get("items", []):
                if e.get("model") == "auto":
                    continue
                out.append({"model": e["model"], "label": e.get("label") or e["model"], "available": bool(e.get("can_forecast")),
                            "reasons": [x for x in [e.get("reason") or e.get("trust_message")] if x][:2], "status": e.get("status"), "trust": e.get("trust"),
                            "trained": bool(e.get("trained")), "test_skill": e.get("test_skill"), "group": g.get("key")})
        return out
    try:
        if is_dhaka(city):
            from app.routing.forecast_costs import recorded_city_data
            cd = recorded_city_data("dhaka")
            cd = cd[0] if isinstance(cd, tuple) else cd
        elif cid and obs_mod.observatory.readiness(cid)["steps_have"] >= 1:
            cd = obs_mod.observatory.city_data(cid)
        else:
            return out + [{"model": m, "label": m, "available": False, "reasons": ["no history for this city yet"]}
                          for m in ("OpenCity-plus", "Chronos-Bolt", "historical_average", "persistence")]
        for m in available_for(cd):
            if m["model"].split("/")[0] in ("STAEformer", "GWNet", "STID"):
                continue                                # benchmark-trained; not for a city's corridors
            out.append({"model": m["model"], "label": m["model"], "available": m["available"], "reasons": m.get("reasons", [])[:2]})
    except (Exception, SystemExit) as exc:              # noqa: BLE001 - the pipeline raises SystemExit for a missing recorded series
        out.append({"model": "Chronos-Bolt", "label": "Chronos-Bolt", "available": False, "reasons": [f"no corridor history available: {exc}"[:200]]})
    return out
