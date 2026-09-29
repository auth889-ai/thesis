"""The assistant's calendar tools: read what is coming, add an event, import a calendar by URL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent.models import RiskClass, new_id
from app.calendar import ics, store

from app.profile import service as profile

LOCAL = timezone(timedelta(hours=ics.LOCAL_UTC_OFFSET_H))   # default only; the tools use the person's zone


def _iso(dt: str, tz=LOCAL) -> str:
    d = datetime.fromisoformat(dt)
    return (d if d.tzinfo else d.replace(tzinfo=tz)).astimezone(timezone.utc).isoformat()


def _local(iso: str, tz=LOCAL) -> str:
    return datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def _view(e: dict, tz=LOCAL) -> dict:
    return {"id": e["id"], "title": e["title"], "start_local": _local(e["start_utc"], tz), "end_local": _local(e["end_utc"], tz), "location": e["location"] or None, "all_day": bool(e["all_day"])}


def upcoming(user_id, a, goal_id):
    tz = profile.tz_for(user_id)
    return {"events": [_view(e, tz) for e in store.upcoming(user_id, float(a.get("hours", 36)))]}


def create_event(user_id, a, goal_id):
    tz = profile.tz_for(user_id)
    start = _iso(a["start"], tz); end = _iso(a["end"], tz) if a.get("end") else (datetime.fromisoformat(start) + timedelta(minutes=int(a.get("minutes", 60)))).isoformat()
    ev = {"uid": new_id("evt"), "title": a["title"], "start_utc": start, "end_utc": end, "location": a.get("location") or "", "all_day": False, "description": a.get("notes") or ""}
    return _view(store.upsert(user_id, ev, "assistant"), tz)


def overlaps(user_id: str, a: dict) -> str | None:
    """Why creating this event needs approval: it would sit on top of something already in the calendar."""
    tz = profile.tz_for(user_id)
    try:
        start = _iso(a["start"], tz); end = _iso(a["end"], tz) if a.get("end") else (datetime.fromisoformat(start) + timedelta(minutes=int(a.get("minutes", 60)))).isoformat()
    except (KeyError, ValueError):
        return None
    for e in store.between(user_id, (datetime.fromisoformat(start) - timedelta(hours=12)).isoformat(), end):
        if e["end_utc"] > start and e["start_utc"] < end:
            return f"it overlaps '{e['title']}' ({_local(e['start_utc'], tz)}–{_local(e['end_utc'], tz)[-5:]})"
    return None


def import_url(user_id, a, goal_id):
    text = ics.fetch(a["url"])
    events = ics.parse(text, profile.tz_for(user_id))
    rows = store.import_events(user_id, events, "ics:" + a["url"][:80])
    store.remember_calendar(user_id, a["url"], a.get("name") or "imported calendar", len(rows))
    return {"imported": len(rows), "next": [_view(e, profile.tz_for(user_id)) for e in store.upcoming(user_id, 48)][:5]}


TOOL_SPECS = [
    ("calendar.upcoming", "The person's calendar events in the coming hours (title, local start and end, location).", {"type": "object", "properties": {"hours": {"type": "number", "default": 36}}, "required": []}, RiskClass.READ, upcoming),
    ("calendar.create_event", "Add an event to the person's calendar. Times are local 'YYYY-MM-DDTHH:MM'.", {"type": "object", "properties": {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "minutes": {"type": "integer", "default": 60}, "location": {"type": "string"}, "notes": {"type": "string"}}, "required": ["title", "start"]}, RiskClass.WRITE_REVERSIBLE, create_event, overlaps),
    ("calendar.import_url", "Import the person's calendar from an iCalendar (.ics / webcal) subscription URL they gave.", {"type": "object", "properties": {"url": {"type": "string"}, "name": {"type": "string"}}, "required": ["url"]}, RiskClass.WRITE_REVERSIBLE, import_url),
]
