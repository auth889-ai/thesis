"""The city map a commuter sees: every observed corridor with its state now and the model's level at
+15/+30/+60, on real road geometry. Computed fresh per request: the live provider draws and, where it
has traffic coverage, prices the roads; the recorded corridor state prices them where it has none; the
forecast is a fresh model run over the recorded window."""
from __future__ import annotations

from datetime import datetime, timezone

HORIZONS = [15, 30, 60]
LEVEL_OF = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5}


def _forecast(city: str) -> tuple[dict, dict, str | None, str | None, str | None]:
    """(predicted level per corridor per horizon, observed levels, as-of, model name, note) for a city with recorded history."""
    from app.routing.forecast_costs import recorded_forecast
    try:
        out = recorded_forecast(city, HORIZONS, None, "latest")
    except (SystemExit, Exception) as exc:              # noqa: BLE001 - no recorded history: the map still draws
        return {}, {}, None, None, f"no forecast: {type(exc).__name__}: {str(exc)[:80]}"
    f = out.get("forecast") or {}
    pred = {}
    for hh in HORIZONS:
        vals = f.get("values", {}).get(hh) or f.get("values", {}).get(str(hh)) or []
        for cid, v in zip(f.get("node_ids", []), vals):
            if v is not None and v == v:
                pred.setdefault(cid, {})[str(hh)] = round(max(0.0, min(3.0, float(v))), 2)
    obs = out.get("observed") or {}
    return pred, dict(obs.get("levels") or {}), obs.get("as_of_utc"), f.get("model"), out.get("note")


def build(city_id: str) -> dict:
    from app.data import reference_corridors as rc
    from app.data.live_providers import live
    from app.routing import local_router
    from app.routing.trip.places import is_dhaka
    defs = [rc.describe(c) for c in rc.CORRIDORS] if is_dhaka(city_id) else []
    if not defs:
        from app.data import city_corridors
        defs = city_corridors.load(city_id)
    if not defs:
        return {"city": city_id, "corridors": [], "status": "NO_CORRIDORS", "note": "no observed corridors for this city yet; plan a trip to see its roads"}
    provider = live.provider()
    snap = provider.corridors_for(city_id) if provider else {"corridors": [], "is_live": False, "traffic_coverage": False}
    live_by_id = {c["id"]: c for c in snap.get("corridors", []) if c.get("is_live")}
    coverage = bool(snap.get("traffic_coverage"))
    pred, observed, as_of, model, note = _forecast("dhaka" if is_dhaka(city_id) else city_id)
    if not live_by_id and local_router.router.available and is_dhaka(city_id):
        levels, as_of_r = local_router.recorded_state("dhaka")
        live_by_id = {c["id"]: c for c in local_router.router.corridors(defs, levels, as_of_r).get("corridors", []) if c.get("segments")}
    corridors = []
    for d in defs:
        c = live_by_id.get(d["id"], {})
        geometry = [pt for s in (c.get("segments") or []) for pt in (s.get("coordinates") or [])] or [[d["origin"]["lat"], d["origin"]["lng"]], [d["destination"]["lat"], d["destination"]["lng"]]]
        live_level = LEVEL_OF.get(c.get("category")) if (coverage and c.get("is_live")) else None
        now = live_level if live_level is not None else observed.get(d["id"])
        corridors.append({"id": d["id"], "name": d.get("name", d["id"]), "road": d.get("road"), "geometry": geometry, "level_now": now,
                          "category_now": "NORMAL" if now is not None and now < 1 else "SLOW" if now is not None and now < 2 else "TRAFFIC_JAM" if now is not None else "UNKNOWN",
                          "live": live_level is not None, "pred": pred.get(d["id"], {}), "distance_m": c.get("distance_m"), "duration_now_s": c.get("duration_s")})
    return {"city": city_id, "computed_utc": datetime.now(timezone.utc).isoformat(), "corridors": corridors, "status": "OK", "model": model, "as_of_utc": as_of, "horizons_min": HORIZONS,
            "provenance": {"roads": f"{snap.get('source', 'frozen OSM network')} ({'live traffic' if coverage else 'no live traffic coverage in this city'})",
                           "now": "live provider" if coverage else f"recorded corridor states as of {as_of}" if as_of else "no recorded state",
                           "forecast": f"{model} on the recorded corridor series (a fresh run for this request)" if model else (note or "no forecast")}}
