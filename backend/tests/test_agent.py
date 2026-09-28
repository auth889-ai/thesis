"""The agent core, run on a scripted model so the loop, the permission engine and the audit log are tested
deterministically. Tools are real (the task store and the commute planner run for real)."""
from __future__ import annotations

import pytest

from app.agent import audit, orchestrator, store, tools
from app.agent.llm import Scripted, Turn
from app.agent.models import Decision, Goal, GoalStatus, RiskClass, ToolCall
from app.agent import permissions


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "agent.sqlite")
    monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path / "audit")


def test_read_tools_run_without_asking_and_everything_is_audited():
    llm = Scripted([Turn(text="I will plan the commute.", tool_calls=[{"name": "mobility__plan_commute", "input": {"origin": "Farmgate", "destination": "Shahbagh", "arrive_by": "2026-10-01T09:00"}, "id": "c1"}]),
                    Turn(text="Leave at the recommended time; the traffic profile is recorded, not live.")])
    g = orchestrator.run(Goal(user_id="u1", text="Be at Shahbagh by 09:00 tomorrow from Farmgate"), llm)
    assert g.status == GoalStatus.DONE and g.steps[0].call.decision == Decision.ALLOW
    assert g.steps[0].call.result["recommended"]["depart_local"]                      # the real planner ran
    kinds = [e["kind"] for e in audit.read("u1", g.id)]
    assert kinds == ["decision", "result", "summary"] and audit.verify("u1")["ok"]
    assert store.load_goal(g.id).status == GoalStatus.DONE                             # durable


def test_irreversible_action_pauses_until_this_exact_call_is_approved():
    t = store.create_task("u2", "submit report", None, None)
    llm = Scripted([Turn(text="Marking it done.", tool_calls=[{"name": "tasks__complete", "input": {"task_id": t["id"]}, "id": "c2"}]), Turn(text="Done.")])
    g = orchestrator.run(Goal(user_id="u2", text=f"Mark task {t['id']} done"), llm)
    assert g.status == GoalStatus.WAITING_APPROVAL and g.steps[0].call.decision == Decision.ASK
    assert store.list_tasks("u2", "open")[0]["status"] == "open"                        # nothing happened yet
    g = orchestrator.approve(g, "c2", True, llm)
    assert g.status == GoalStatus.DONE and store.list_tasks("u2", "done")[0]["id"] == t["id"]
    assert [e["kind"] for e in audit.read("u2", g.id)] == ["decision", "approval", "result", "summary"]


def test_declined_approval_is_logged_and_the_action_never_runs():
    t = store.create_task("u3", "x", None, None)
    llm = Scripted([Turn(text="", tool_calls=[{"name": "tasks__complete", "input": {"task_id": t["id"]}, "id": "c3"}]), Turn(text="Understood, left open.")])
    g = orchestrator.run(Goal(user_id="u3", text=f"complete {t['id']}"), llm)
    g = orchestrator.approve(g, "c3", False, llm)
    assert g.status == GoalStatus.DONE and store.list_tasks("u3", "open") and g.steps[0].call.error == "declined by the user"


def test_the_model_must_ask_instead_of_guessing_and_the_answer_resumes_the_goal():
    llm = Scripted([Turn(text="I need the arrival time.", tool_calls=[{"name": "user__ask", "input": {"question": "By what time must you arrive?"}, "id": "q1"}]),
                    Turn(text="Planning.", tool_calls=[{"name": "mobility__plan_commute", "input": {"origin": "Farmgate", "destination": "Shahbagh", "arrive_by": "2026-10-01T09:30"}, "id": "c4"}]),
                    Turn(text="Planned.")])
    g = orchestrator.run(Goal(user_id="u4", text="Plan my commute Farmgate to Shahbagh"), llm)
    assert g.status == GoalStatus.WAITING_USER and g.steps[0].question
    g = orchestrator.answer(g, "q1", "09:30", llm)
    assert g.status == GoalStatus.DONE and "09:30" in str(g.steps[1].call.arguments)


def test_invented_sensitive_arguments_are_refused_not_asked():
    call = ToolCall(tool="email.send", arguments={"to": "boss@example.com", "body": "hi"})
    d, why = permissions.decide(call, RiskClass.EXTERNAL, known_context="send my report to my supervisor")
    assert d == Decision.REFUSE and "invented" in why
    d2, _ = permissions.decide(call, RiskClass.EXTERNAL, known_context="send it to boss@example.com")
    assert d2 == Decision.ASK


def test_tool_specs_come_from_the_registry():
    names = {s["toolSpec"]["name"] for s in tools.tool_specs()}
    assert {"mobility__plan_commute", "tasks__create", "tasks__complete", "reminders__create", "user__ask"} <= names
    assert all("inputSchema" in s["toolSpec"] for s in tools.tool_specs())


def test_endpoints_without_a_model_say_so_honestly(client, monkeypatch):
    from app.agent import router as agent_router
    agent_router._llm.cache_clear()
    monkeypatch.setattr(agent_router, "_llm", lambda: (_ for _ in ()).throw(RuntimeError("no model")))
    r = client.post("/api/agent/goals", json={"user_id": "demo", "text": "plan my day"})
    assert r.status_code == 503 and "language model unavailable" in r.json()["detail"]
    assert client.get("/api/agent/tools").status_code == 200 and client.get("/api/agent/audit?user_id=demo").status_code == 200
