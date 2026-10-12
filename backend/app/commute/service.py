"""COMMUTE PLANNER — "leave at 7:46, 87 % chance of arriving by 9:00", from the city's OWN observed history.

Given a trip (origin, destination, target arrival), evaluate every candidate departure time and report the latest
one that still arrives on time with high probability, the route to take, and the day's profile on that route.

How the numbers are made, and what they are NOT:
  travel time at a departure  = the route's free-flow time (real roads from Amazon Location, or the frozen OSM
                                network as a fallback) × the travel-time multipliers the worst corridor the route
                                runs along has shown at that time of day in THIS CITY'S OWN observed history
                                (our own opt-in phone sensing; route-provider speeds are never read)
  on-time probability         = share of those observed multipliers whose travel time meets the deadline minus a
                                safety buffer (an empirical probability, not a model's confidence)
  no history on the route     = no probability is shown, the response says why, and the route can be watched so
                                its history starts accumulating
"""
from __future__ import annotations

import math
import threading
from datetime import datetime, timedelta, timezone

from core.common.paths import REPO
from app.commute import history

BAND = {0: 1.08, 1: 1.33, 2: 1.75, 3: 2.50}          # the congestion multipliers the trip analysis uses for an unobserved route
SLOT_MIN = history.SLOT_MIN
SLOTS = history.SLOTS
LOCAL_UTC_OFFSET_H = 6                                 # Dhaka, the deployment default when a person has no zone
ON_TIME_TARGET = 0.80
_LOCK = threading.Lock()
MATCH_M = 400                                          # a route touches a city corridor when both ends sit within this of the corridor's ends


# ------------------------------------------------------------------ this city's own observed profile
def profile(corridor: str, city: str = "dhaka", tz_offset_h: float = LOCAL_UTC_OFFSET_H) -> dict:
    """One corridor's own time-of-day profile: expected multiplier and the share of slow-or-worse readings per slot."""
    prof = history.own_profiles(_city_id(city), tz_offset_h)
    out = []
    for sl in range(SLOTS):
        vals = history.multiplier_distribution(prof, corridor, sl, neighbours=0)
        out.append({"slot": sl, "time": f"{sl * SLOT_MIN // 60:02d}:{sl * SLOT_MIN % 60:02d}", "samples": len(prof["corridors"].get(corridor, {}).get(sl, [])),
                    "expected_level": round(history.level_of(float(sum(vals) / len(vals))), 2) if vals else None,
                    "p_slow_or_worse": round(sum(1 for v in vals if v >= 1.2) / len(vals), 3) if vals else None})
    return {"corridor": corridor, "slot_min": SLOT_MIN, "local_utc_offset_h": tz_offset_h, "slots": out,
            "provenance": {"kind": "OWN_OBSERVED" if prof["samples"] else "NO_OBSERVED_TRAFFIC", "source": "results/live/observatory.sqlite (own phone sensing only)", "samples_total": prof["samples"],
                           "first_utc": prof["first_utc"], "last_utc": prof["last_utc"], "note": prof["rule"]}}


def _city_id(city: str) -> str:
    from core.simulation.routing.trip.places import city_id_for
    return city_id_for(city) or "".join(ch if ch.isalnum() else "_" for ch in (city or "").lower()).strip("_")


# ------------------------------------------------------------------ the plan
def _slot_of(t: datetime, tz_offset_h: float = LOCAL_UTC_OFFSET_H) -> int:
    lt = t.astimezone(timezone.utc) + timedelta(hours=tz_offset_h)
    return (lt.hour * 60 + lt.minute) // SLOT_MIN


def _routes(city: str, origin: str, destination: str) -> tuple[dict, dict, list[dict], dict]:
    from core.common.data import reference_corridors as rc
    from core.simulation.routing import local_router
    from core.simulation.routing.trip_analysis import resolve_place
    o, d = resolve_place(origin, city), resolve_place(destination, city)
    defs = [rc.describe(c) for c in rc.CORRIDORS]
    state = {}
    for c in defs:
        try:
            edges = local_router.router.corridor_route(c["id"], (c["origin"]["lat"], c["origin"]["lng"]), (c["destination"]["lat"], c["destination"]["lng"]))
        except LookupError:
            edges = []
        if edges:
            state[c["id"]] = {"edges": set(e.getID() for e in edges), "level": None}
    from core.common.data.live_providers import live
    from core.simulation.routing.trip.geometry import runs_along
    provider = live.provider()
    r = provider.routes((o["lat"], o["lng"]), (d["lat"], d["lng"])) if provider else {"routes": []}
    if r.get("routes"):
        # real roads and free-flow times from the provider; which recorded corridors each route runs along, by geometry
        polys = {cid: local_router.router._geometry(local_router.router.corridor_route(cid, (c["origin"]["lat"], c["origin"]["lng"]), (c["destination"]["lat"], c["destination"]["lng"])))
                 for cid, c in ((c["id"], c) for c in defs) if cid in state}
        for route in r["routes"]:
            pts = [tuple(p) for p in route.get("geometry") or []]
            route["corridors_touched"] = sorted(cid for cid, poly in polys.items() if len(poly) >= 2 and runs_along(pts, [tuple(p) for p in poly]))
            route["description"] = route.get("description") or f"{round(route.get('distance_m', 0) / 1000, 1)} km via the provider's road network"
        r["routing_words"] = f"real roads and free-flow times from {live.WORDS[r['source']]['traffic']}"
    else:
        r = local_router.router.routes((o["lat"], o["lng"]), (d["lat"], d["lng"]), state, None)
        r["routing_words"] = "free-flow times on the frozen OSM/SUMO network at posted limits — minutes are uncalibrated, compare departures and routes, not clocks"
    if not r.get("routes"):
        raise ValueError(f"no route between {origin} and {destination}: {r.get('request_status')}")
    cid = _city_id(city)
    if cid != "dhaka":                                   # another city's corridors: the routes people asked about, matched by their ends
        from core.common.data import city_corridors
        from core.common.data.city_corridors import _dist as haversine_m
        for route in r["routes"]:
            touched = []
            for c in city_corridors.load(cid):
                if haversine_m((o["lat"], o["lng"]), (c["origin"]["lat"], c["origin"]["lng"])) <= MATCH_M and \
                        haversine_m((d["lat"], d["lng"]), (c["destination"]["lat"], c["destination"]["lng"])) <= MATCH_M:
                    touched.append(c["id"])
            route["corridors_touched"] = sorted(set(route.get("corridors_touched") or []) | set(touched))
    state["_routing_words"] = r["routing_words"]
    return o, d, r["routes"], state


def _route_time_distribution(route: dict, slot: int, profiles: dict) -> tuple[dict[float, float] | None, str | None, float | None]:
    """travel-time distribution of a route at a slot: free-flow time × the multipliers of the WORST touched corridor
    in the city's own history; (None, None, None) when no touched corridor has been observed at that slot."""
    static = float(route["static_duration_s"]); worst_name, worst = None, None
    for cid in route.get("corridors_touched") or []:
        vals = history.multiplier_distribution(profiles, cid, slot)
        if vals and (worst is None or sum(vals) / len(vals) > sum(worst) / len(worst)):
            worst_name, worst = cid, vals
    if worst is None:
        return None, None, None
    dist: dict[float, float] = {}
    for m in worst:
        k = round(static * m); dist[k] = dist.get(k, 0.0) + 1.0 / len(worst)
    return dist, worst_name, float(sum(worst) / len(worst))


def plan(city: str, origin: str, destination: str, arrive_by: datetime, buffer_min: int = 5, step_min: int = 10, now: datetime | None = None, tz=None, target: float = ON_TIME_TARGET) -> dict:
    """`tz` is the person's zone for the local clock strings; `target` the on-time probability they asked for."""
    tz = tz or timezone(timedelta(hours=LOCAL_UTC_OFFSET_H))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    off = (tz.utcoffset(now) or timedelta(0)).total_seconds() / 3600
    cid = _city_id(city)
    profiles = history.own_profiles(cid, off)
    arrive_by = arrive_by.astimezone(timezone.utc) if arrive_by.tzinfo else arrive_by.replace(tzinfo=timezone.utc)
    if arrive_by <= now:
        raise ValueError("arrive_by must be in the future")
    o, d, routes, state = _routes(city, origin, destination)
    budget_floor = min(float(r["static_duration_s"]) for r in routes)
    departures = []
    t = now.replace(second=0, microsecond=0)
    while t + timedelta(seconds=budget_floor) <= arrive_by:
        slot = _slot_of(t, off); budget = (arrive_by - t).total_seconds() - buffer_min * 60; opts = []
        for r in routes:
            dist, worst, _ = _route_time_distribution(r, slot, profiles)
            if dist is None:
                opts.append({"route": r_key(r, routes), "covered": False, "expected_s": round(float(r["static_duration_s"]) * BAND[0]), "on_time_probability": None, "worst_corridor": None})
                continue
            exp = sum(s * p for s, p in dist.items()); p_ok = sum(p for s, p in dist.items() if s <= budget)
            opts.append({"route": r_key(r, routes), "covered": True, "expected_s": round(exp), "on_time_probability": round(p_ok, 3), "worst_corridor": worst})
        best = max(opts, key=lambda x: ((x["on_time_probability"] or 0.0), -x["expected_s"]))
        departures.append({"depart_utc": t.isoformat(), "depart_local": t.astimezone(tz).strftime("%H:%M"), "slot": slot, "budget_s": round(budget), "best_route": best["route"], "on_time_probability": best["on_time_probability"], "expected_s": best["expected_s"], "options": opts})
        t += timedelta(minutes=step_min)
    if not departures:
        raise ValueError("no departure can reach the destination before arrive_by even in free flow")
    ok = [x for x in departures if (x["on_time_probability"] or 0) >= target]
    rec = ok[-1] if ok else max(departures, key=lambda x: ((x["on_time_probability"] or 0), x["depart_utc"]))
    rec_route = next(r for r in routes if r_key(r, routes) == rec["best_route"])
    # the day's profile on the recommended route, and the congestion window in the coming 12 hours
    day = []
    for s in range(SLOTS):
        dist, worst, mean_m = _route_time_distribution(rec_route, s, profiles)
        exp_level = history.level_of(mean_m) if mean_m is not None else None
        day.append({"slot": s, "time": f"{s * SLOT_MIN // 60:02d}:{s * SLOT_MIN % 60:02d}", "expected_s": round(sum(v * p for v, p in dist.items())) if dist else None, "expected_level": round(exp_level, 2) if exp_level is not None else None})
    # congestion window: the longest run of SLOW-or-worse slots in the coming 12 hours (falls back to a softer threshold)
    now_slot = _slot_of(now, off); window = None
    for threshold in (1.0, 0.8, 0.6):
        runs, cur = [], None
        for k in range(SLOTS // 2):
            s = (now_slot + k) % SLOTS; lvl = day[s]["expected_level"]
            if lvl is not None and lvl >= threshold:
                cur = cur or {"from": day[s]["time"], "to": day[s]["time"], "peak_level": lvl, "slots": 0}
                cur["to"] = day[s]["time"]; cur["peak_level"] = max(cur["peak_level"], lvl); cur["slots"] += 1
            elif cur:
                runs.append(cur); cur = None
        if cur:
            runs.append(cur)
        if runs:
            best = max(runs, key=lambda w: (w["slots"], w["peak_level"]))
            window = {"from": best["from"], "to": best["to"], "peak_level": round(best["peak_level"], 2), "threshold": threshold}
            break
    from core.common.data.live_providers.observatory import observatory
    own = observatory.own_history(cid) if cid in observatory.cities() else {"steps_own": 0}
    touched = sorted({c for r in routes for c in (r.get("corridors_touched") or [])})
    covered_any = any(x["covered"] for dpt in departures for x in dpt["options"])
    coverage = {"city_id": cid, "watched": cid in observatory.cities(), "steps_own": own.get("steps_own", 0), "corridors_touched": touched,
                "covered": covered_any, "samples": profiles["samples"], "first_utc": profiles["first_utc"], "last_utc": profiles["last_utc"],
                "action": None if covered_any else "no observed traffic for this city yet: it appears once people here share their position while moving (Map → Your phone is the sensor)"}
    return {"city": city, "origin": o, "destination": d, "arrive_by_utc": arrive_by.isoformat(), "arrive_by_local": arrive_by.astimezone(tz).strftime("%H:%M"), "now_utc": now.isoformat(), "buffer_min": buffer_min, "on_time_target": target,
            "recommended": {"depart_utc": rec["depart_utc"], "depart_local": rec["depart_local"], "route": rec["best_route"], "on_time_probability": rec["on_time_probability"], "expected_s": rec["expected_s"], "leave_in_min": round((datetime.fromisoformat(rec["depart_utc"]) - now).total_seconds() / 60)},
            "routes": [{"key": r_key(r, routes), "description": r.get("description"), "distance_m": r.get("distance_m"), "static_s": r.get("static_duration_s"), "corridors": r.get("corridors_touched") or [],
                        "now": next(x for x in departures[0]["options"] if x["route"] == r_key(r, routes)), "at_departure": next(x for x in rec["options"] if x["route"] == r_key(r, routes))} for r in routes],
            "departures": departures, "day_profile": day, "congestion_window": window, "coverage": coverage,
            "provenance": {"kind": "OWN_OBSERVED" if covered_any else "ROUTING_ONLY",
                           "traffic": (f"this city's own observed history: {profiles['samples']} corridor readings from {str(profiles['first_utc'])[:16]} to {str(profiles['last_utc'])[:16]} UTC, from opt-in phone sensing"
                                       if covered_any else "no observed traffic for this city yet: every time shown is a free-flow route time; no probability is shown because none can be measured yet"),
                           "routing": state.get("_routing_words", ""),
                           "probability": "share of this city's own observed travel-time multipliers at that time of day meeting the deadline minus the buffer (empirical), not a model confidence"}}


def r_key(route: dict, routes: list[dict]) -> str:
    return "ABC"[routes.index(route)] if routes.index(route) < 3 else str(routes.index(route))


def watch_route(city: str, origin: str, destination: str) -> dict:
    """The road a person asked about becomes an observed corridor of its city from now on, and the city is watched."""
    from core.common.data import city_corridors
    from core.common.data.live_providers.observatory import observatory
    from core.simulation.routing.trip_analysis import resolve_place
    cid = _city_id(city)
    o, d = resolve_place(origin, city), resolve_place(destination, city)
    added = []
    if cid != "dhaka":
        city_corridors.ensure(cid)
        before = {c["id"] for c in city_corridors.load(cid)}
        after = city_corridors.add_routes(cid, [{"label": f"{origin} to {destination}", "origin": {"lat": o["lat"], "lng": o["lng"]}, "destination": {"lat": d["lat"], "lng": d["lng"]}}])
        added = [c["id"] for c in after if c["id"] not in before]
    status = observatory.start(cid)
    history.forget(cid)
    return {"city_id": cid, "watched": True, "corridors_added": added, "recorder": status, "next": "readings arrive every 5 minutes; the plan shows a probability once this route has readings at the times of day asked about"}
