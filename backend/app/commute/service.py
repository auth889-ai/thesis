"""COMMUTE PLANNER — "leave at 7:46, 87 % chance of arriving by 9:00".

Given a saved commute (origin, destination, target arrival), evaluate every candidate departure time and
report the latest one that still arrives on time with high probability, the route to take, and the
day's traffic profile on that route.

How the numbers are made, and what they are NOT:
  travel time at a departure  = free-flow time of the route on the frozen OSM/SUMO network (posted limits)
                                × the congestion multiplier of the worst corridor the route runs along,
                                weighted by the RECORDED distribution of that corridor's congestion level
                                at that time of day (TYPICAL_RECORDED: the project's own recorded history,
                                every 15-minute slot, several days) — never a live measurement
  on-time probability         = share of that recorded distribution whose travel time meets the deadline
                                minus a safety buffer (an empirical probability, not a model's confidence)
  congestion window           = the slots of the coming hours whose expected level is SLOW or worse
Absolute minutes are uncalibrated (the network's posted limits are optimistic); the ranking of departures
and routes is what the planner is for, and every response says so.
"""
from __future__ import annotations

import json
import math
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.paths import REPO

RECORDED = REPO / "results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl"
LEVEL = {"FREE_FLOW": 0, "SLOW": 1, "CONGESTED": 2, "SEVERE": 3}
LEVEL_NAME = {v: k for k, v in LEVEL.items()}
BAND = {0: 1.08, 1: 1.33, 2: 1.75, 3: 2.50}          # the same congestion multipliers the trip analysis uses
SLOT_MIN = 15
SLOTS = 24 * 60 // SLOT_MIN
LOCAL_UTC_OFFSET_H = 6                                 # the recorded Dhaka corridor profiles are binned in Dhaka local time
ON_TIME_TARGET = 0.80
_LOCK = threading.Lock()


# ------------------------------------------------------------------ recorded time-of-day profile
@lru_cache(maxsize=1)
def _profiles() -> dict:
    """corridor -> {slot -> [level, ...]} from the recorded history (local time of day)."""
    if not RECORDED.exists():
        return {"corridors": {}, "samples": 0, "first_utc": None, "last_utc": None}
    per: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list)); n = 0; first = last = None
    for line in RECORDED.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        lvl = LEVEL.get(r.get("congestion_state") or "")
        if lvl is None or not r.get("corridor_id") or not r.get("captured_utc"):
            continue
        t = datetime.fromisoformat(r["captured_utc"].replace("Z", "+00:00")) + timedelta(hours=LOCAL_UTC_OFFSET_H)
        per[r["corridor_id"]][(t.hour * 60 + t.minute) // SLOT_MIN].append(lvl); n += 1
        first = min(first, r["captured_utc"]) if first else r["captured_utc"]; last = max(last, r["captured_utc"]) if last else r["captured_utc"]
    return {"corridors": {c: dict(s) for c, s in per.items()}, "samples": n, "first_utc": first, "last_utc": last}


def level_distribution(corridor: str, slot: int, neighbours: int = 1) -> dict[int, float] | None:
    """p(level) at a slot, pooling ±neighbours slots so a thin slot still has a distribution; None if unrecorded."""
    prof = _profiles()["corridors"].get(corridor)
    if not prof:
        return None
    vals: list[int] = []
    for k in range(-neighbours, neighbours + 1):
        vals += prof.get((slot + k) % SLOTS, [])
    if not vals:
        return None
    return {l: vals.count(l) / len(vals) for l in sorted(set(vals))}


def profile(corridor: str) -> dict:
    out = []
    for s in range(SLOTS):
        d = level_distribution(corridor, s, neighbours=0)
        out.append({"slot": s, "time": f"{s * SLOT_MIN // 60:02d}:{s * SLOT_MIN % 60:02d}", "samples": len(_profiles()["corridors"].get(corridor, {}).get(s, [])),
                    "expected_level": round(sum(l * p for l, p in d.items()), 2) if d else None, "p_slow_or_worse": round(sum(p for l, p in d.items() if l >= 1), 3) if d else None})
    meta = _profiles()
    return {"corridor": corridor, "slot_min": SLOT_MIN, "local_utc_offset_h": LOCAL_UTC_OFFSET_H, "slots": out,
            "provenance": {"kind": "TYPICAL_RECORDED", "source": str(RECORDED.relative_to(REPO)), "samples_total": meta["samples"], "first_utc": meta["first_utc"], "last_utc": meta["last_utc"],
                           "note": "recorded congestion classes by local time of day; not a live measurement"}}


# ------------------------------------------------------------------ the plan
def _slot_of(t: datetime) -> int:
    lt = t.astimezone(timezone.utc) + timedelta(hours=LOCAL_UTC_OFFSET_H)
    return (lt.hour * 60 + lt.minute) // SLOT_MIN


def _routes(city: str, origin: str, destination: str) -> tuple[dict, dict, list[dict], dict]:
    from app.data import reference_corridors as rc
    from app.routing import local_router
    from app.routing.trip_analysis import resolve_place
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
    from app.data.live_providers import live
    from app.routing.trip.geometry import runs_along
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
    state["_routing_words"] = r["routing_words"]
    return o, d, r["routes"], state


def _route_time_distribution(route: dict, slot: int) -> tuple[dict[float, float] | None, str | None]:
    """travel-time distribution of a route at a slot: free-flow × band of the WORST touched corridor's level."""
    static = float(route["static_duration_s"]); worst_name, worst = None, None
    for cid in route.get("corridors_touched") or []:
        d = level_distribution(cid, slot)
        if d and (worst is None or sum(l * p for l, p in d.items()) > sum(l * p for l, p in worst.items())):
            worst_name, worst = cid, d
    if worst is None:
        return None, None
    return {round(static * BAND[l]): p for l, p in worst.items()}, worst_name


def plan(city: str, origin: str, destination: str, arrive_by: datetime, buffer_min: int = 5, step_min: int = 10, now: datetime | None = None, tz=None, target: float = ON_TIME_TARGET) -> dict:
    """`tz` is the person's zone for the local clock strings; `target` the on-time probability they asked for."""
    tz = tz or timezone(timedelta(hours=LOCAL_UTC_OFFSET_H))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    arrive_by = arrive_by.astimezone(timezone.utc) if arrive_by.tzinfo else arrive_by.replace(tzinfo=timezone.utc)
    if arrive_by <= now:
        raise ValueError("arrive_by must be in the future")
    o, d, routes, state = _routes(city, origin, destination)
    budget_floor = min(float(r["static_duration_s"]) for r in routes)
    departures = []
    t = now.replace(second=0, microsecond=0)
    while t + timedelta(seconds=budget_floor) <= arrive_by:
        slot = _slot_of(t); budget = (arrive_by - t).total_seconds() - buffer_min * 60; opts = []
        for r in routes:
            dist, worst = _route_time_distribution(r, slot)
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
        dist, worst = _route_time_distribution(rec_route, s)
        exp_level = None
        if worst:
            dl = level_distribution(worst, s); exp_level = sum(l * p for l, p in dl.items()) if dl else None
        day.append({"slot": s, "time": f"{s * SLOT_MIN // 60:02d}:{s * SLOT_MIN % 60:02d}", "expected_s": round(sum(v * p for v, p in dist.items())) if dist else None, "expected_level": round(exp_level, 2) if exp_level is not None else None})
    # congestion window: the longest run of SLOW-or-worse slots in the coming 12 hours (falls back to a softer threshold)
    now_slot = _slot_of(now); window = None
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
    meta = _profiles()
    return {"city": city, "origin": o, "destination": d, "arrive_by_utc": arrive_by.isoformat(), "arrive_by_local": arrive_by.astimezone(tz).strftime("%H:%M"), "now_utc": now.isoformat(), "buffer_min": buffer_min, "on_time_target": target,
            "recommended": {"depart_utc": rec["depart_utc"], "depart_local": rec["depart_local"], "route": rec["best_route"], "on_time_probability": rec["on_time_probability"], "expected_s": rec["expected_s"], "leave_in_min": round((datetime.fromisoformat(rec["depart_utc"]) - now).total_seconds() / 60)},
            "routes": [{"key": r_key(r, routes), "description": r.get("description"), "distance_m": r.get("distance_m"), "static_s": r.get("static_duration_s"), "corridors": r.get("corridors_touched") or [],
                        "now": next(x for x in departures[0]["options"] if x["route"] == r_key(r, routes)), "at_departure": next(x for x in rec["options"] if x["route"] == r_key(r, routes))} for r in routes],
            "departures": departures, "day_profile": day, "congestion_window": window,
            "provenance": {"kind": "TYPICAL_RECORDED", "traffic": f"recorded congestion classes of {len(meta['corridors'])} Dhaka corridors by local time of day ({meta['samples']} samples, {str(meta['first_utc'])[:10]} to {str(meta['last_utc'])[:10]}); not live",
                           "routing": state.get("_routing_words", ""),
                           "probability": "share of the recorded distribution meeting the deadline minus the buffer (empirical), not a model confidence"}}


def r_key(route: dict, routes: list[dict]) -> str:
    return "ABC"[routes.index(route)] if routes.index(route) < 3 else str(routes.index(route))
