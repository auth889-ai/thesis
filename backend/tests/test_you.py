"""Everything about a person can be exported as one document and erased in one call (agent/you.py)."""
from __future__ import annotations

import pytest

from app.agent import audit, memory, store, you
from app.calendar import store as cal_store
from app.plan import notifications, outcomes


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "agent.sqlite"); monkeypatch.setattr(memory, "DB", tmp_path / "memory.sqlite")
    monkeypatch.setattr(cal_store, "DB", tmp_path / "calendar.sqlite"); monkeypatch.setattr(notifications, "DB", tmp_path / "n.sqlite")
    monkeypatch.setattr(outcomes, "DB", tmp_path / "o.sqlite"); monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path / "audit")


def _fill(user):
    store.create_task(user, "t", None, "goal_x"); store.create_reminder(user, "r", "2026-10-01T02:00:00+00:00", "goal_x"); store.save_commute(user, "work", "A", "B", "09:00")
    memory.remember(user, "prefers rail", "preference"); cal_store.upsert(user, {"uid": "e", "title": "Viva", "start_utc": "2026-10-02T04:00:00+00:00", "end_utc": "2026-10-02T05:00:00+00:00", "location": "IUT", "all_day": False, "description": ""}, "test")
    notifications.publish(user, "departure", "leave earlier"); outcomes.record(user, "ref", "A", "B", 600, None, "2026-09-29T02:00:00+00:00", "2026-09-29T02:12:00+00:00", "2026-09-29T02:30:00+00:00")
    from app.agent.models import AuditEntry
    audit.write(AuditEntry(user_id=user, goal_id="goal_x", kind="summary", detail={"text": "done"}))


def test_export_holds_every_store_and_erase_empties_them_for_that_person_only():
    _fill("p1"); _fill("p2")
    e = you.export("p1")
    assert len(e["tasks"]) == 1 and len(e["reminders"]) == 1 and len(e["commutes"]) == 1 and len(e["memory"]) == 1 and len(e["events"]) == 1
    assert len(e["notifications"]) == 1 and len(e["outcomes"]) == 1 and len(e["audit"]) == 1 and e["audit_chain"]["ok"]
    r = you.erase("p1")
    assert r["agent"]["tasks"] == 1 and r["memory"] == 1 and r["calendar"]["events"] == 1 and r["outcomes"] == 1 and r["notifications"] == 1 and r["audit_files"] == 2
    gone = you.export("p1")
    assert not gone["tasks"] and not gone["memory"] and not gone["events"] and not gone["audit"]
    still = you.export("p2")
    assert len(still["tasks"]) == 1 and len(still["audit"]) == 1                              # the other person is untouched


def test_erase_over_http_needs_the_confirmation(client):
    assert client.delete("/api/you?user_id=p3").status_code == 400
    assert client.delete("/api/you?user_id=p3&confirm=p3").json()["user_id"] == "p3"
    assert client.get("/api/you/export?user_id=p3").json()["tasks"] == []


def test_a_goal_lists_what_it_created(client):
    store.create_task("p4", "bring forms", None, "goal_a"); store.create_task("p4", "other", None, "goal_b")
    g = __import__("app.agent.models", fromlist=["Goal"]).Goal(user_id="p4", text="x"); g.id = "goal_a"; store.save_goal(g)
    r = client.get("/api/agent/goals/goal_a/related").json()
    assert [t["title"] for t in r["tasks"]] == ["bring forms"] and r["reminders"] == []
