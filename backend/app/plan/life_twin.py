"""The person's situation as one snapshot: commitments, deadlines, departures, free windows, routines,
preferences and calibration — and the feasibility check: can this day physically work, given how long each
journey between two placed commitments is expected to take?"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent import memory, store
from app.calendar import store as cal
from app.plan import day, outcomes
from app.plan import conflicts as conf
from app.plan import feasibility as feas

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
    """Each gap between placed commitments graded feasible / risky / impossible / unknown (plan/feasibility.py)."""
    return feas.assess(user_id, events)


def snapshot(user_id: str, hours: float = 48.0) -> dict:
    now = datetime.now(timezone.utc)
    events = cal.upcoming(user_id, hours, now)
    tasks = [t for t in store.list_tasks(user_id, "open") if not t["due_utc"] or _dt(t["due_utc"]) <= now + timedelta(hours=hours)]
    checks = feasibility(user_id, events)
    deps = day.departures(user_id, hours, now)
    return {"user_id": user_id, "now_utc": now.isoformat(), "hours": hours,
            "commitments": [{"id": e["id"], "title": e["title"], "start_utc": e["start_utc"], "end_utc": e["end_utc"], "location": e["location"] or None, "all_day": bool(e["all_day"])} for e in events],
            "deadlines": [{"id": t["id"], "title": t["title"], "due_utc": t["due_utc"]} for t in tasks],
            "departures": deps, "free_windows": free_windows(events, now, hours), "conflicts": conf.find(events, tasks, deps, checks),
            "routines": store.list_commutes(user_id), "preferences": [m["text"] for m in memory.list_all(user_id)][:12],
            "calibration": outcomes.calibration(user_id), "feasibility": checks,
            "verdict": feas.verdict(checks)}
