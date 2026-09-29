"""The assistant's calendar tools: read what is coming, add an event, import a calendar by URL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent.models import RiskClass, new_id
from app.calendar import ics, store

LOCAL = timezone(timedelta(hours=ics.LOCAL_UTC_OFFSET_H))


def _iso(dt: str) -> str:
    d = datetime.fromisoformat(dt)
    return (d if d.tzinfo else d.replace(tzinfo=LOCAL)).astimezone(timezone.utc).isoformat()


def _local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(LOCAL).strftime("%Y-%m-%dT%H:%M")


def _view(e: dict) -> dict:
    return {"id": e["id"], "title": e["title"], "start_local": _local(e["start_utc"]), "end_local": _local(e["end_utc"]), "location": e["location"] or None, "all_day": bool(e["all_day"])}


def upcoming(user_id, a, goal_id):
    return {"events": [_view(e) for e in store.upcoming(user_id, float(a.get("hours", 36)))]}


def create_event(user_id, a, goal_id):
    start = _iso(a["start"]); end = _iso(a["end"]) if a.get("end") else (datetime.fromisoformat(start) + timedelta(minutes=int(a.get("minutes", 60)))).isoformat()
    ev = {"uid": new_id("evt"), "title": a["title"], "start_utc": start, "end_utc": end, "location": a.get("location") or "", "all_day": False, "description": a.get("notes") or ""}
    return _view(store.upsert(user_id, ev, "assistant"))


def import_url(user_id, a, goal_id):
    text = ics.fetch(a["url"])
    events = ics.parse(text)
    rows = store.import_events(user_id, events, "ics:" + a["url"][:80])
    store.remember_calendar(user_id, a["url"], a.get("name") or "imported calendar", len(rows))
    return {"imported": len(rows), "next": [_view(e) for e in store.upcoming(user_id, 48)][:5]}


TOOL_SPECS = [
    ("calendar.upcoming", "The person's calendar events in the coming hours (title, local start and end, location).", {"type": "object", "properties": {"hours": {"type": "number", "default": 36}}, "required": []}, RiskClass.READ, upcoming),
    ("calendar.create_event", "Add an event to the person's calendar. Times are local 'YYYY-MM-DDTHH:MM'.", {"type": "object", "properties": {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "minutes": {"type": "integer", "default": 60}, "location": {"type": "string"}, "notes": {"type": "string"}}, "required": ["title", "start"]}, RiskClass.WRITE_REVERSIBLE, create_event),
    ("calendar.import_url", "Import the person's calendar from an iCalendar (.ics / webcal) subscription URL they gave.", {"type": "object", "properties": {"url": {"type": "string"}, "name": {"type": "string"}}, "required": ["url"]}, RiskClass.WRITE_REVERSIBLE, import_url),
]
