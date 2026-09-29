"""The day as one timeline: events, tasks due, reminders, and a fresh departure plan for every event with a place
and every saved commute whose arrival is still ahead. Each departure is computed now, with the person's own
calibration applied to the travel-time distribution."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent import store
from app.calendar import store as cal
from app.plan import outcomes

LOCAL = timezone(timedelta(hours=6))
HOME = "home"


def _local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(LOCAL).strftime("%H:%M")


def departure_for(user_id: str, origin: str, destination: str, arrive_by: datetime, ref: str, title: str, city: str = "dhaka") -> dict:
    """One departure plan, or the reason there is none. Never raises."""
    from app.commute import service
    factor = outcomes.calibration(user_id)["factor"]
    try:
        p = service.plan(city, origin, destination, arrive_by, now=datetime.now(timezone.utc))
        rec = p["recommended"]
        expected = round(rec["expected_s"] * factor)
        depart = datetime.fromisoformat(rec["depart_utc"])
        if factor != 1.0:                                   # a slower-than-predicted person leaves earlier by the same share
            depart = depart - timedelta(seconds=expected - rec["expected_s"])
        return {"ref": ref, "title": title, "origin": origin, "destination": destination, "arrive_by_utc": arrive_by.isoformat(), "arrive_by_local": arrive_by.astimezone(LOCAL).strftime("%H:%M"),
                "depart_utc": depart.isoformat(), "depart_local": depart.astimezone(LOCAL).strftime("%H:%M"), "route": rec["route"], "on_time_probability": rec["on_time_probability"],
                "expected_s": expected, "calibration_factor": factor, "leave_in_min": round((depart - datetime.now(timezone.utc)).total_seconds() / 60), "status": "OK", "provenance": p["provenance"]}
    except Exception as exc:                                # noqa: BLE001 - the timeline still shows the event
        return {"ref": ref, "title": title, "origin": origin, "destination": destination, "arrive_by_utc": arrive_by.isoformat(), "status": f"no plan: {type(exc).__name__}: {str(exc)[:100]}"}


def departures(user_id: str, hours: float = 24.0, now: datetime | None = None, origin: str | None = None) -> list[dict]:
    """A departure for every upcoming event with a location, and every saved commute whose arrival is still ahead."""
    now = now or datetime.now(timezone.utc)
    origin = origin or _home(user_id)
    out = []
    for e in cal.upcoming(user_id, hours, now):
        if e["location"] and not e["all_day"] and datetime.fromisoformat(e["start_utc"]) > now:
            out.append(departure_for(user_id, origin, e["location"], datetime.fromisoformat(e["start_utc"]), f"event:{e['id']}", e["title"]))
    for cmt in store.list_commutes(user_id):
        h, m = (cmt["arrive_by_local"] or "09:00").split(":")[:2]
        local_now = now.astimezone(LOCAL); arrive = local_now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if arrive <= local_now:
            arrive += timedelta(days=1)
        if (arrive - local_now) <= timedelta(hours=hours):
            out.append(departure_for(user_id, cmt["origin"], cmt["destination"], arrive.astimezone(timezone.utc), f"commute:{cmt['id']}", cmt["name"]))
    return sorted(out, key=lambda d: d.get("depart_utc") or d["arrive_by_utc"])


def _home(user_id: str) -> str:
    """The person's usual origin: a remembered place, else the origin of their first saved commute, else the default place."""
    from app.agent import memory
    for f in memory.list_all(user_id):
        if f["kind"] == "place" and f["text"].lower().startswith(("home", "i live")):
            return f["text"].split(":", 1)[-1].split(" is ", 1)[-1].strip(" .") or HOME
    c = store.list_commutes(user_id)
    return c[0]["origin"] if c else "Farmgate"


def timeline(user_id: str, hours: float = 24.0) -> dict:
    now = datetime.now(timezone.utc)
    items = []
    for e in cal.upcoming(user_id, hours, now):
        items.append({"at_utc": e["start_utc"], "at_local": _local(e["start_utc"]), "kind": "event", "title": e["title"], "detail": e["location"] or "", "id": e["id"], "all_day": bool(e["all_day"])})
    for t in store.list_tasks(user_id, "open"):
        if t["due_utc"] and now - timedelta(hours=1) <= datetime.fromisoformat(t["due_utc"]) <= now + timedelta(hours=hours):
            items.append({"at_utc": t["due_utc"], "at_local": _local(t["due_utc"]), "kind": "task", "title": t["title"], "detail": "due", "id": t["id"]})
    for r in store.list_reminders(user_id, "scheduled"):
        if now - timedelta(hours=1) <= datetime.fromisoformat(r["at_utc"]) <= now + timedelta(hours=hours):
            items.append({"at_utc": r["at_utc"], "at_local": _local(r["at_utc"]), "kind": "reminder", "title": r["text"], "detail": "", "id": r["id"]})
    deps = departures(user_id, hours, now)
    for d in deps:
        if d["status"] == "OK":
            items.append({"at_utc": d["depart_utc"], "at_local": d["depart_local"], "kind": "leave", "title": f"Leave for {d['title']}", "detail": f"route {d['route']} · {round(d['expected_s'] / 60)} min · {round((d['on_time_probability'] or 0) * 100)} % on time", "id": d["ref"], "departure": d})
    items.sort(key=lambda x: x["at_utc"])
    return {"user_id": user_id, "now_utc": now.isoformat(), "hours": hours, "items": items, "departures": deps, "calibration": outcomes.calibration(user_id)}
