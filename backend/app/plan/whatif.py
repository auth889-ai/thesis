"""'What if I leave at 8:30?' — the consequence of one departure time, from the same distribution the planner
uses, beside the road and rail options at that time. Also the recovery plan when a departure was missed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent.models import RiskClass
from app.plan import day

LOCAL = day.LOCAL


def _iso_local(dt: str) -> datetime:
    d = datetime.fromisoformat(dt)
    return (d if d.tzinfo else d.replace(tzinfo=LOCAL)).astimezone(timezone.utc)


def evaluate(city: str, origin: str, destination: str, arrive_by: datetime, depart_at: datetime, user_id: str = "demo") -> dict:
    """The candidate departure nearest to `depart_at`: expected arrival, on-time probability, and the best option then."""
    from app.commute import service
    from app.plan import outcomes
    from app.transit import service as transit
    from app.routing.trip.places import resolve_place
    p = service.plan(city, origin, destination, arrive_by, step_min=5, now=min(datetime.now(timezone.utc), depart_at - timedelta(minutes=1)))
    factor = outcomes.calibration(user_id)["factor"]
    slot = min(p["departures"], key=lambda d: abs(datetime.fromisoformat(d["depart_utc"]) - depart_at))
    expected = round(slot["expected_s"] * factor)
    arrival = depart_at + timedelta(seconds=expected)
    rec = p["recommended"]
    o, d = resolve_place(origin, city), resolve_place(destination, city)
    rail = transit.plan((o["lat"], o["lng"]), (d["lat"], d["lng"]), depart_at, 6.0)
    best_rail = next((x for x in rail["options"] if x["open"]), None)
    late_min = round((arrival - arrive_by).total_seconds() / 60)
    return {"depart_local": depart_at.astimezone(LOCAL).strftime("%H:%M"), "arrive_by_local": arrive_by.astimezone(LOCAL).strftime("%H:%M"),
            "road": {"route": slot["best_route"], "expected_min": round(expected / 60), "expected_arrival_local": arrival.astimezone(LOCAL).strftime("%H:%M"), "on_time_probability": slot["on_time_probability"], "late_by_min": max(0, late_min)},
            "rail": ({"line": best_rail["line"], "total_min": round(best_rail["total_s"] / 60), "expected_arrival_local": (depart_at + timedelta(seconds=best_rail["total_s"])).astimezone(LOCAL).strftime("%H:%M"),
                      "on_time": (depart_at + timedelta(seconds=best_rail["total_s"])) <= arrive_by} if best_rail else None),
            "recommended_depart_local": rec["depart_local"], "recommended_on_time_probability": rec["on_time_probability"],
            "verdict": _verdict(slot["on_time_probability"], late_min, best_rail is not None and (depart_at + timedelta(seconds=best_rail["total_s"])) <= arrive_by, rec["depart_local"]),
            "provenance": p["provenance"]}


def _verdict(p_ok: float | None, late_min: int, rail_ok: bool, rec_local: str) -> str:
    if p_ok is not None and p_ok >= 0.8:
        return f"leaving then still arrives on time with {round(p_ok * 100)} % confidence"
    if rail_ok:
        return "the road is risky at that time; the rail option still arrives before the deadline"
    if late_min > 0:
        return f"leaving then arrives about {late_min} min late; leave by {rec_local} instead"
    return f"leaving then is a gamble ({round((p_ok or 0) * 100)} % on time); leave by {rec_local} instead"


def recovery(user_id: str, city: str, origin: str, destination: str, arrive_by: datetime) -> dict:
    """The person is still where they were after the planned departure: what is the best move now?"""
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    return {"kind": "recovery", **evaluate(city, origin, destination, arrive_by, now, user_id)}


def tool_what_if(user_id, a, goal_id):
    return evaluate(a.get("city", "dhaka"), a["origin"], a["destination"], _iso_local(a["arrive_by"]), _iso_local(a["depart_at"]), user_id)


TOOL_SPECS = [("mobility.what_if", "What happens if the person leaves at a given time: expected arrival, on-time probability, the rail alternative, and a verdict. Times local 'YYYY-MM-DDTHH:MM'.",
               {"type": "object", "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}, "arrive_by": {"type": "string"}, "depart_at": {"type": "string"}, "city": {"type": "string", "default": "dhaka"}}, "required": ["origin", "destination", "arrive_by", "depart_at"]},
               RiskClass.READ, tool_what_if)]
