"""Approvals are bound to one exact action, expire, can become standing rules, and a rejection carries the
person's reason to the model (agent/approvals.py); the audit log carries signed checkpoints (agent/audit.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.agent import approvals, audit, orchestrator, store, tools
from app.agent.llm import Scripted, Turn
from app.agent.models import Decision, Goal, GoalStatus
from app.calendar import store as cal_store


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "agent.sqlite")
    monkeypatch.setattr(cal_store, "DB", tmp_path / "calendar.sqlite")
    monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path / "audit")


def _complete_task(user, text="Done."):
    t = store.create_task(user, "x", None, None)
    llm = Scripted([Turn(text="", tool_calls=[{"name": "tasks__complete", "input": {"task_id": t["id"]}, "id": "c1"}]), Turn(text=text)])
    return t, llm, orchestrator.run(Goal(user_id=user, text=f"complete {t['id']}"), llm)


def test_a_paused_call_carries_its_action_hash_and_expiry():
    t, llm, g = _complete_task("u1")
    c = g.steps[0].call
    assert g.status == GoalStatus.WAITING_APPROVAL and c.action_hash == approvals.action_hash("tasks.complete", {"task_id": t["id"]})
    assert datetime.fromisoformat(c.approval_expires_utc) > datetime.now(timezone.utc)
    assert store.load_goal(g.id).steps[0].call.action_hash == c.action_hash                 # durable


def test_an_approval_for_a_different_action_is_not_accepted():
    t, llm, g = _complete_task("u2")
    with pytest.raises(ValueError, match="changed since you saw it"):
        orchestrator.approve(g, "c1", True, llm, action_hash="0000000000000000")
    assert store.list_tasks("u2", "open")                                                   # nothing ran
    g = orchestrator.approve(g, "c1", True, llm, action_hash=g.steps[0].call.action_hash)
    assert g.status == GoalStatus.DONE and store.list_tasks("u2", "done")


def test_an_expired_approval_is_refused_and_the_model_is_told():
    t, llm, g = _complete_task("u3")
    g.steps[0].call.approval_expires_utc = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(); store.save_goal(g)
    with pytest.raises(ValueError, match="expired"):
        orchestrator.approve(g, "c1", True, llm)
    g = orchestrator.run(g, llm)                                                            # resuming moves on: the call errored, the model replied
    assert g.steps[0].call.error.startswith("not approved within") and g.status == GoalStatus.DONE
    assert store.list_tasks("u3", "open")


def test_a_rejection_message_reaches_the_model():
    t, llm, g = _complete_task("u4", text="Left it open as you asked.")
    g = orchestrator.approve(g, "c1", False, llm, message="not yet, the report is not submitted")
    assert g.steps[0].call.error == "declined by the user: not yet, the report is not submitted"
    tool_results = [m for m in orchestrator._messages(g) if m["role"] == "user" and "toolResult" in m["content"][0]]
    assert "not yet, the report is not submitted" in str(tool_results[0])
    assert audit.read("u4", g.id)[1]["detail"]["message"] == "not yet, the report is not submitted"


def test_always_turns_one_decision_into_a_standing_rule_that_is_audited_when_used():
    t, llm, g = _complete_task("u5")
    g = orchestrator.approve(g, "c1", True, llm, always=True)
    assert approvals.list_rules("u5") == [{"user_id": "u5", "tool": "tasks.complete", "decision": "approve", "created_utc": approvals.list_rules("u5")[0]["created_utc"], "source_goal": g.id}]
    t2, llm2, g2 = _complete_task("u5")
    assert g2.status == GoalStatus.DONE and g2.steps[0].call.decision == Decision.ALLOW and "every time" in g2.steps[0].call.decision_reason
    assert [e["kind"] for e in audit.read("u5", g2.id)][:2] == ["approval", "decision"] and audit.read("u5", g2.id)[0]["detail"]["by"] == "standing rule"
    assert approvals.clear_rule("u5", "tasks.complete") and not approvals.list_rules("u5")
    _, _, g3 = _complete_task("u5")
    assert g3.status == GoalStatus.WAITING_APPROVAL


def test_a_standing_reject_refuses_without_asking():
    approvals.set_rule("u6", "tasks.complete", "reject", None)
    _, _, g = _complete_task("u6")
    assert g.steps[0].call.decision == Decision.REFUSE and store.list_tasks("u6", "open")


def test_a_tool_predicate_escalates_an_allowed_call_to_approval():
    tools._register_domains()
    cal_store.upsert("u7", {"uid": "e1", "title": "Viva", "start_utc": "2026-10-02T04:00:00+00:00", "end_utc": "2026-10-02T05:00:00+00:00", "location": "", "all_day": False, "description": ""}, "test")
    llm = Scripted([Turn(text="", tool_calls=[{"name": "calendar__create_event", "input": {"title": "Dentist", "start": "2026-10-02T10:30", "minutes": 60}, "id": "c1"}]), Turn(text="Added.")])
    g = orchestrator.run(Goal(user_id="u7", text="dentist 10:30 on 2 Oct"), llm)
    assert g.status == GoalStatus.WAITING_APPROVAL and g.steps[0].call.decision == Decision.ASK and "overlaps 'Viva'" in g.steps[0].call.decision_reason
    llm2 = Scripted([Turn(text="", tool_calls=[{"name": "calendar__create_event", "input": {"title": "Lunch", "start": "2026-10-03T12:00"}, "id": "c2"}]), Turn(text="Added.")])
    g2 = orchestrator.run(Goal(user_id="u7", text="lunch"), llm2)
    assert g2.status == GoalStatus.DONE and g2.steps[0].call.decision == Decision.ALLOW


def test_signed_checkpoints_catch_a_rechained_log(tmp_path):
    t, llm, g = _complete_task("u8")
    g = orchestrator.approve(g, "c1", True, llm)
    v = audit.verify("u8")
    assert v["ok"] and v["checkpoint"]["signed_ok"] and v["checkpoint"]["matches_chain"]
    path = audit._file("u8"); rows = [l for l in path.read_text().splitlines() if l.strip()]
    import hashlib, json
    doctored = []; prev = "genesis"                                                        # rewrite history AND re-chain it
    for l in rows:
        r = json.loads(l); r["detail"] = {**r["detail"], "approved": False} if r["kind"] == "approval" else r["detail"]; r["prev"] = prev
        body = {k: v for k, v in r.items() if k != "hash"}; r["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]; prev = r["hash"]; doctored.append(json.dumps(r))
    path.write_text("\n".join(doctored) + "\n")
    v = audit.verify("u8")
    assert not v["ok"] and v["checkpoint"]["signed_ok"] and not v["checkpoint"]["matches_chain"]
