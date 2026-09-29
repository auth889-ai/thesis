"""The person's day: calendar import, memory recall, the timeline with departures, the monitor's change detection, outcomes calibration."""
from datetime import datetime, timedelta, timezone

import pytest

ICS = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:abc@test\r\nDTSTART;TZID=Asia/Dhaka:20261001T100000\r\nDTEND;TZID=Asia/Dhaka:20261001T110000\r\nSUMMARY:Interview\\, final round\r\nLOCATION:Motijheel\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:day@test\r\nDTSTART;VALUE=DATE:20261002\r\nSUMMARY:Holiday\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:utc@test\r\nDTSTART:20261001T030000Z\r\nSUMMARY:Standup\r\nDESCRIPTION:line one\\nline\r\n  two\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""


@pytest.fixture
def user(tmp_path, monkeypatch):
    from app.agent import store
    monkeypatch.setattr(store, "DB", tmp_path / "agent.sqlite")
    for mod in ("app.agent.memory", "app.calendar.store", "app.plan.notifications", "app.plan.outcomes", "app.plan.monitor"):
        monkeypatch.setattr(__import__(mod, fromlist=["DB"]), "DB", tmp_path / "agent.sqlite")
    return "u-test"


def test_ics_reader_handles_zones_dates_and_folded_lines():
    from app.calendar import ics
    ev = {e["uid"]: e for e in ics.parse(ICS)}
    assert ev["abc@test"]["start_utc"] == "2026-10-01T04:00:00+00:00" and ev["abc@test"]["location"] == "Motijheel" and ev["abc@test"]["title"] == "Interview, final round"
    assert ev["day@test"]["all_day"] is True and ev["utc@test"]["start_utc"].startswith("2026-10-01T03:00:00") and ev["utc@test"]["description"] == "line one\nline two"


def test_import_updates_by_uid_and_lists_upcoming(user):
    from app.calendar import ics, store
    rows = store.import_events(user, ics.parse(ICS), "ics:test")
    again = store.import_events(user, ics.parse(ICS.replace("Interview\\, final round", "Interview (moved)")), "ics:test")
    assert len(rows) == 3 and {r["id"] for r in rows} == {r["id"] for r in again}
    up = store.upcoming(user, 48, now=datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc))
    assert [e["title"] for e in up][:2] == ["Standup", "Interview (moved)"]


def test_memory_recalls_relevant_facts_and_constraints_first(user):
    from app.agent import memory
    memory.remember(user, "Prefers reliability over the shortest route", "preference")
    memory.remember(user, "Wants a 15-minute buffer before interviews", "constraint")
    memory.remember(user, "Home is Farmgate", "place")
    memory.remember(user, "Studies in 90-minute focus blocks", "pattern")
    got = memory.recall(user, "plan my route to the interview", limit=2)
    assert got[0]["kind"] == "constraint" and "interview" in got[0]["text"].lower()
    assert "What you know about this person" in memory.prompt_section(user, "interview")
    assert memory.forget(user, got[0]["id"]) and len(memory.list_all(user)) == 3


def test_timeline_has_a_departure_for_an_event_with_a_place(user, monkeypatch):
    from app.calendar import store as cal
    from app.plan import day
    start = (datetime.now(timezone.utc) + timedelta(hours=3)).replace(microsecond=0)
    cal.upsert(user, {"uid": "e1", "title": "Viva", "start_utc": start.isoformat(), "end_utc": start.isoformat(), "location": "Shahbagh"}, "test")
    from app.commute import service
    monkeypatch.setattr(service, "plan", lambda city, o, d, arrive_by, **kw: {"recommended": {"depart_utc": (arrive_by - timedelta(minutes=40)).isoformat(), "route": "A", "on_time_probability": 0.9, "expected_s": 1800}, "provenance": {"traffic": "t", "routing": "r", "probability": "p"}})
    t = day.timeline(user, 24)
    kinds = [i["kind"] for i in t["items"]]
    assert kinds == ["leave", "event"] and t["items"][0]["title"] == "Leave for Viva" and t["departures"][0]["status"] == "OK"
    assert t["calibration"]["factor"] == 1.0


def test_monitor_tells_the_person_when_a_departure_moves(user, monkeypatch):
    from app.plan import monitor, notifications
    prev = {"depart_utc": "2026-10-01T02:00:00+00:00", "on_time_probability": 0.9, "route": "A"}
    cur = {"status": "OK", "title": "Viva", "depart_utc": "2026-10-01T01:48:00+00:00", "depart_local": "07:48", "on_time_probability": 0.85, "route": "A"}
    assert "Leave earlier" in monitor.compare(prev, cur)
    assert monitor.compare(prev, {**cur, "depart_utc": prev["depart_utc"], "on_time_probability": 0.6}).startswith("Traffic on the way")
    assert monitor.compare(prev, {**cur, "depart_utc": prev["depart_utc"], "on_time_probability": 0.9, "route": "B"}).startswith("Better route")
    assert monitor.compare(prev, {**cur, "depart_utc": "2026-10-01T02:01:00+00:00", "on_time_probability": 0.9}) is None
    n = notifications.publish(user, "departure", "hello")
    assert n["delivered"] == "in-app" and notifications.list_for(user)[0]["read_utc"] is None
    assert notifications.mark_read(user) == 1


def test_outcomes_calibrate_after_three_trips(user):
    from app.plan import outcomes
    for k in range(3):
        outcomes.record(user, f"t{k}", "Farmgate", "Shahbagh", 600, None, "2026-10-01T02:00:00+00:00", "2026-10-01T02:15:00+00:00", "2026-10-01T02:30:00+00:00")
    c = outcomes.calibration(user)
    assert c["trips"] == 3 and c["factor"] == 1.5 and c["on_time_rate"] == 1.0
