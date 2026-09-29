"""FEASIBILITY — can the person physically get from one commitment to the next?

For every consecutive pair of placed commitments the commute planner's on-time distribution is asked one
question: leaving the moment the first one ends, what is the probability of arriving before the second starts?
    feasible    p >= TARGET (0.8)                       the gap holds
    risky       RISKY (0.5) <= p < TARGET               it can work, but not reliably
    impossible  p < RISKY                               it does not fit as it stands
    unknown     no plan could be made (a place could not be resolved, no provider)
`buffer_min` is how many minutes before the first commitment ends the person must leave to reach TARGET: the
recommended departure against the end time. It is computed from the same distribution the departure advice uses,
and scaled by the person's calibration like every departure (plan/day.py). Nothing here is a fixed number."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from app.plan import outcomes
from app.profile import service as profile

TARGET, RISKY = 0.8, 0.5                                 # TARGET is the default; the person's own target is used when set
GRADES = ("feasible", "risky", "impossible", "unknown")


def grade(p_ok: float | None, target: float = TARGET) -> str:
    if p_ok is None:
        return "unknown"
    return "feasible" if p_ok >= target else "risky" if p_ok >= RISKY else "impossible"


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _default_plan(city, origin, destination, arrive_by, now, user_id=None):
    from app.commute import service
    return service.plan(city, origin, destination, arrive_by, step_min=5, now=now, tz=profile.tz_for(user_id), target=profile.target_for(user_id))


def check_pair(user_id: str, prev: dict, nxt: dict, city: str | None = None, plan: Callable = _default_plan, now: datetime | None = None) -> dict:
    """One gap: the grade, the probability when leaving as the first ends, the journey time, and the buffer needed."""
    now = now or datetime.now(timezone.utc); city = city or profile.city_for(user_id); target = profile.target_for(user_id)
    end, start = _dt(prev["end_utc"]), _dt(nxt["start_utc"])
    gap_min = round((start - end).total_seconds() / 60)
    base = {"from": prev["title"], "to": nxt["title"], "gap_min": gap_min}
    try:
        p = plan(city, prev["location"], nxt["location"], start, min(now, end)) if plan is not _default_plan else plan(city, prev["location"], nxt["location"], start, min(now, end), user_id)
    except Exception as exc:                                        # noqa: BLE001 - the check is shown with its reason
        return base | {"grade": "unknown", "feasible": None, "needed_min": None, "p_at_end": None, "buffer_min": None, "note": f"no plan: {type(exc).__name__}: {str(exc)[:80]}"}
    factor = outcomes.calibration(user_id)["factor"]
    at_end = min(p["departures"], key=lambda d: abs(_dt(d["depart_utc"]) - end))
    p_ok = at_end["on_time_probability"]
    needed = round(at_end["expected_s"] * factor / 60)
    rec = p["recommended"]; rec_depart = _dt(rec["depart_utc"])
    buffer_min = max(0, round((end - rec_depart).total_seconds() / 60))
    g = grade(p_ok, target)
    note = {"feasible": f"fits: leaving as it ends arrives with {round((p_ok or 0) * 100)} % confidence",
            "risky": f"tight: {gap_min} min between them, the journey needs about {needed} min; leaving as it ends is {round((p_ok or 0) * 100)} % on time — leave {buffer_min} min before the end to be safe",
            "impossible": f"does not fit: {gap_min} min between them but the journey needs about {needed} min ({round((p_ok or 0) * 100)} % on time); it would take leaving {buffer_min} min before the end",
            "unknown": "no probability available"}[g]
    return base | {"grade": g, "feasible": g == "feasible", "needed_min": needed, "p_at_end": p_ok, "buffer_min": buffer_min, "depart_local": rec["depart_local"], "on_time_probability": rec["on_time_probability"], "route": at_end.get("best_route"), "note": note}


def assess(user_id: str, events: list[dict], city: str | None = None, plan: Callable = _default_plan, now: datetime | None = None) -> list[dict]:
    """Every consecutive pair of placed, timed commitments, in order."""
    placed = sorted((e for e in events if e.get("location") and not e.get("all_day")), key=lambda e: e["start_utc"])
    return [check_pair(user_id, a, b, city, plan, now) for a, b in zip(placed, placed[1:])]


def verdict(checks: list[dict]) -> str:
    grades = [c["grade"] for c in checks]
    if not grades:
        return "no placed commitments to check"
    if "impossible" in grades:
        return "this schedule does not fit as it stands"
    if "risky" in grades:
        return "this schedule can work, but one gap is tight"
    if all(g == "unknown" for g in grades):
        return "no gap could be checked"
    return "this schedule can work"
