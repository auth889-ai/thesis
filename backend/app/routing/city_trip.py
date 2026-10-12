"""One trip in one city, as the home screen shows it: the route on the city's own network, each section's real speed
now and its forecast where either exists, and the travel time at each departure the slider offers.

A recorded reading from a published dataset is given only when a clock time is asked for, in its own field with
its own date; it takes no part in the travel times.

Nothing is guessed. A section without a real reading has no speed. A departure with no section covered has no travel
time; the page then shows only the drive time at the map's speed limits, which is tagged as a simulation that is
calibrated to nothing. Where only part of the route is covered, the rest is counted at its speed limit and the tag
says what share of the route's length the traffic data covers.
"""
from __future__ import annotations

from pathlib import Path

from core.common import tag
from core.common.data import real_speeds
from app.data import probe_speeds
from core.ml.forecasting.operations import section_forecast
from core.simulation.routing import city_router

LIMITS_BASIS = "every section driven at its map speed limit; no traffic, signals or queues"
REST = "the rest of the route is counted at its map speed limit"


def _minutes(sections: list[dict], speed_of) -> float:
    return sum(s["length_m"] / 1000 / max(speed_of(s), 1.0) * 60 for s in sections)


def travel(sections: list[dict], stop: str) -> dict | None:
    """Travel time when leaving at a slider stop ("0" is now), or None when no section has data for it."""
    value = lambda s: s["now"] if stop == "0" else s["forecast"].get(stop)
    covered = [s for s in sections if value(s)]
    if not covered:
        return None
    share = round(sum(s["length_m"] for s in covered) / sum(s["length_m"] for s in sections), 3)
    first = value(covered[0])["tag"]
    t = {**first, "covers_share_of_length": share, "rest": REST, "sections_with_data": len(covered), "sections": len(sections)}
    out = tag.tagged(round(_minutes(sections, lambda s: value(s)["value"] if value(s) else s["limit_kmh"]), 1), "min", t)
    if stop != "0":                                     # slow end of every forecast range gives the long end of the time range
        out["range"] = [round(_minutes(sections, lambda s: value(s)["range"][i] if value(s) else s["limit_kmh"]), 1) for i in (1, 0)]
    return out


def trip(city_id: str, origin: tuple[float, float], dest: tuple[float, float], now=None, db_url: str | None = None, adapter=None,
         city_dir: Path = city_router.CITY_DIR, recorded_at: str | None = None) -> dict:
    try:
        r = city_router.route(city_id, origin, dest, city_dir)
    except city_router.Refused as no:
        return {"city_id": city_id, "available": False, "code": no.code, "note": no.message}
    net, man = city_router.network(city_id, str(city_dir))
    readings = probe_speeds.read(city_id, net, [net.getEdge(s["id"]) for s in r["sections"]], man["bbox"], now, db_url)
    forecasts, why_not = section_forecast.forecast(city_id, readings, "this section's own readings from phones that opted in", adapter) if readings else ({}, "no_readings")
    for s in r["sections"]:
        got = readings.get(s["id"])
        s["now"] = tag.tagged(got["kmh"], "km/h", got["tag"]) if got else None
        s["forecast"] = forecasts.get(s["id"], {})
    past = real_speeds.recorded(city_id, net, [net.getEdge(s["id"]) for s in r["sections"]], man["bbox"], recorded_at) if recorded_at else {}
    for s in r["sections"]:
        s["recorded"] = past.get(s["id"])               # a past measurement with its own date; never part of `now`, `forecast` or `travel`
    stops = ["0"] + [str(h) for h in section_forecast.HORIZONS_MIN]
    return {**r, "available": True, "from": {"lat": origin[0], "lon": origin[1]}, "to": {"lat": dest[0], "lon": dest[1]},
            "horizons_min": [int(x) for x in stops],
            "at_limits": tag.tagged(round(_minutes(r["sections"], lambda s: s["limit_kmh"]), 1), "min", tag.simulated(LIMITS_BASIS)),
            "travel": {stop: travel(r["sections"], stop) for stop in stops},
            "traffic": "partial" if readings else "none", "no_forecast_because": why_not,
            "sources": probe_speeds.sources(city_id, man["bbox"], db_url),
            "recorded": {"at": recorded_at, "sources": real_speeds.recorded_sources(city_id, net, man["bbox"])}}
