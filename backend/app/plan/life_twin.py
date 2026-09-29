"""The person's situation as one snapshot: commitments, deadlines, departures, free windows, routines,
preferences and calibration — and the feasibility check: can this day physically work, given how long each
journey between two placed commitments is expected to take?"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent import memory, store
from app.calendar import store as cal
from app.plan import day, outcomes

WAKING = (6, 23)             # local hours in which a gap counts as free time
MIN_FREE_MIN = 30


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def free_windows(events: list[dict], now: datetime, hours: float) -> list[dict]:
    """Gaps of at least MIN_FREE_MIN between timed commitments, within waking hours, in local time."""
    end = now + timedelta(hours=hours)
    busy = sorted(((_dt(e["start_utc"]), _dt(e["end_utc"])) for e in events if not e["all_day"]), key=lambda x: x[0])
    out, cursor = [], now
    for a, b in busy + [(end, end)]:
        if a - cursor >= timedelta(minutes=MIN_FREE_MIN):
            la, lb = cursor.astimezone(day.LOCAL), min(a, end).astimezone(day.LOCAL)
            if WAKING[0] <= la.hour < WAKING[1]:
                out.append({"from_local": la.strftime("%a %H:%M"), "to_local": lb.strftime("%a %H:%M"), "minutes": round((min(a, end) - cursor).total_seconds() / 60)})
        cursor = max(cursor, b)
    return out


def feasibility(user_id: str, events: list[dict]) -> list[dict]:
    """For every consecutive pair of placed commitments: the gap, the journey the planner expects, and whether it fits."""
    placed = [e for e in events if e["location"] and not e["all_day"]]
    checks = []
    for prev, nxt in zip(placed, placed[1:]):
        gap_min = (_dt(nxt["start_utc"]) - _dt(prev["end_utc"])).total_seconds() / 60
        d = day.departure_for(user_id, prev["location"], nxt["location"], _dt(nxt["start_utc"]), f"leg:{prev['id']}-{nxt['id']}", nxt["title"])
        if d["status"] != "OK":
            checks.append({"from": prev["title"], "to": nxt["title"], "gap_min": round(gap_min), "needed_min": None, "feasible": None, "note": d["status"]})
            continue
        needed = round(d["expected_s"] / 60)
        ok = _dt(d["depart_utc"]) >= _dt(prev["end_utc"])
        checks.append({"from": prev["title"], "to": nxt["title"], "gap_min": round(gap_min), "needed_min": needed, "depart_local": d["depart_local"], "on_time_probability": d["on_time_probability"], "feasible": ok,
                       "note": ("fits" if ok else f"only {round(gap_min)} min between them but the journey needs about {needed} min to arrive with {round((d['on_time_probability'] or 0) * 100)} % confidence")})
    return checks


def snapshot(user_id: str, hours: float = 48.0) -> dict:
    now = datetime.now(timezone.utc)
    events = cal.upcoming(user_id, hours, now)
    tasks = [t for t in store.list_tasks(user_id, "open") if not t["due_utc"] or _dt(t["due_utc"]) <= now + timedelta(hours=hours)]
    checks = feasibility(user_id, events)
    return {"user_id": user_id, "now_utc": now.isoformat(), "hours": hours,
            "commitments": [{"id": e["id"], "title": e["title"], "start_utc": e["start_utc"], "end_utc": e["end_utc"], "location": e["location"] or None, "all_day": bool(e["all_day"])} for e in events],
            "deadlines": [{"id": t["id"], "title": t["title"], "due_utc": t["due_utc"]} for t in tasks],
            "departures": day.departures(user_id, hours, now), "free_windows": free_windows(events, now, hours),
            "routines": store.list_commutes(user_id), "preferences": [m["text"] for m in memory.list_all(user_id)][:12],
            "calibration": outcomes.calibration(user_id), "feasibility": checks,
            "verdict": ("no placed commitments to check" if not checks else "this schedule can work" if all(c["feasible"] for c in checks if c["feasible"] is not None) else "this schedule does not fit as it stands")}
