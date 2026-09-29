"""YOU — everything the system holds about one person, exportable as one document and erasable in one call.
Each domain store knows how to erase its own rows for a user; this module only asks them in order and reports
what was removed, so no store reaches into another's tables."""
from __future__ import annotations

from app.agent import approvals, audit, memory, store
from app.calendar import store as calendar_store
from app.plan import monitor, notifications, outcomes
from app.profile import store as profile_store


def export(user_id: str) -> dict:
    """One JSON document: goals, tasks, reminders, commutes, standing decisions, memory, calendar, outcomes, notifications, audit."""
    return {"user_id": user_id, "exported_utc": store.now_iso(), "profile": profile_store.get(user_id),
            "goals": [store.load_goal(g["id"]).to_dict() for g in store.list_goals(user_id, limit=10_000)],
            "tasks": store.list_tasks(user_id, None), "reminders": store.list_reminders(user_id, None), "commutes": store.list_commutes(user_id),
            "approval_rules": approvals.list_rules(user_id), "memory": memory.list_all(user_id),
            "calendars": calendar_store.list_calendars(user_id), "events": calendar_store.between(user_id, "0000", "9999"),
            "outcomes": outcomes.list_for(user_id, limit=10_000), "notifications": notifications.list_for(user_id, limit=10_000),
            "audit": audit.read(user_id, limit=10**9), "audit_chain": audit.verify(user_id)}


def erase(user_id: str) -> dict:
    """Remove the person's data from every store; the counts say what was there. Irreversible."""
    return {"user_id": user_id, "erased_utc": store.now_iso(),
            "agent": store.erase_user(user_id), "memory": memory.erase_user(user_id), "calendar": calendar_store.erase_user(user_id),
            "outcomes": outcomes.erase_user(user_id), "notifications": notifications.erase_user(user_id), "watch": monitor.erase_user(user_id),
            "profile": profile_store.erase_user(user_id), "audit_files": audit.erase_user(user_id)}
