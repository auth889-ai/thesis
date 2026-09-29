"""Goals run in the background under a lease, can be cancelled, and survive a restart (agent/worker.py)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.agent import audit, orchestrator, store, worker
from app.agent.llm import Scripted, Turn
from app.agent.models import Goal, GoalStatus, Step, ToolCall, now_iso


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "agent.sqlite")
    monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path / "audit")


def _llm(text="Done."):
    return lambda: Scripted([Turn(text="", tool_calls=[{"name": "tasks__create", "input": {"title": "pack the bag"}, "id": "c1"}]), Turn(text=text)])


def test_a_goal_runs_in_the_background_and_the_lease_is_released():
    g = Goal(user_id="w1", text="pack"); g.status = GoalStatus.RUNNING; store.save_goal(g)
    assert worker.enqueue(g.id, _llm()) and worker.state()["running"] == [g.id]
    done = worker.wait(g.id)
    assert done.status == GoalStatus.DONE and store.list_tasks("w1")[0]["title"] == "pack the bag"
    assert not store.lease_alive(g.id) and worker.state()["running"] == []


def test_only_one_runner_holds_a_goal_until_its_lease_lapses():
    g = Goal(user_id="w2", text="x"); store.save_goal(g)
    assert store.claim_lease(g.id, "other-host:1", (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat())
    assert worker.enqueue(g.id, _llm()) is False                                        # someone live owns it
    with store._LOCK, store._conn() as c:
        c.execute("update goal_leases set until_utc=? where goal_id=?", ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), g.id))
    g.status = GoalStatus.RUNNING; store.save_goal(g)
    assert worker.enqueue(g.id, _llm()) and worker.wait(g.id).status == GoalStatus.DONE


def test_a_cancel_request_stops_the_goal_at_its_next_step():
    g = Goal(user_id="w3", text="x"); g.status = GoalStatus.RUNNING; store.save_goal(g)
    store.request_cancel(g.id)
    worker.enqueue(g.id, _llm()); done = worker.wait(g.id)
    assert done.status == GoalStatus.CANCELLED and done.summary == "stopped by you" and not store.list_tasks("w3")
    assert [e["kind"] for e in audit.read("w3", g.id)] == ["cancel"]


def test_a_paused_goal_is_cancelled_at_once():
    t = store.create_task("w4", "x", None, None)
    llm = Scripted([Turn(text="", tool_calls=[{"name": "tasks__complete", "input": {"task_id": t["id"]}, "id": "c1"}])])
    g = orchestrator.run(Goal(user_id="w4", text="complete"), llm)
    assert g.status == GoalStatus.WAITING_APPROVAL
    assert worker.cancel(g.id).status == GoalStatus.CANCELLED and store.list_tasks("w4", "open")


def test_an_interrupted_goal_is_recovered_after_a_restart():
    g = Goal(user_id="w5", text="pack"); g.status = GoalStatus.RUNNING
    call = ToolCall(tool="tasks.create", arguments={"title": "pack the bag"}, id="c0"); call.started_utc = now_iso()   # in flight when the process died
    g.steps.append(Step(thought="creating", call=call)); store.save_goal(g)
    store.claim_lease(g.id, "dead-host:9", (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat())   # its lease lapsed
    resumed = worker.resume_interrupted(_llm("Recovered."))
    assert resumed == [g.id]
    done = worker.wait(g.id)
    assert done.status == GoalStatus.DONE and done.summary == "Recovered."
    assert done.steps[0].call.error.startswith("interrupted by a restart") and done.steps[0].call.finished_utc
    kinds = [e["kind"] for e in audit.read("w5", g.id)]
    assert kinds[0] == "interrupted" and "summary" in kinds
    msgs = orchestrator._messages(done)                                                # the model was told, not misled
    assert "interrupted by a restart" in str(msgs)


def test_a_goal_with_a_live_lease_is_left_alone_on_restart():
    g = Goal(user_id="w6", text="x"); g.status = GoalStatus.RUNNING; store.save_goal(g)
    store.claim_lease(g.id, "alive-host:2", (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat())
    assert worker.resume_interrupted(_llm()) == []


def test_the_api_returns_at_once_and_the_page_can_poll(client, monkeypatch):
    from app.agent import router as agent_router
    llm = Scripted([Turn(text="", tool_calls=[{"name": "intent__record", "input": {"goal_type": "other", "objectives": ["x"], "domains": ["tasks"]}, "id": "i"}]),
                    Turn(text="", tool_calls=[{"name": "tasks__create", "input": {"title": "call the dentist"}, "id": "c1"}]), Turn(text="Added.")])
    monkeypatch.setattr(agent_router, "_llm", lambda: llm)
    r = client.post("/api/agent/goals", json={"user_id": "w7", "text": "call the dentist"}).json()
    assert r["status"] == "running"
    worker.wait(r["id"])
    g = client.get(f"/api/agent/goals/{r['id']}").json()
    assert g["status"] == "done" and g["summary"] == "Added."
    assert client.get("/api/agent/worker").json()["running"] == []
    assert client.post(f"/api/agent/goals/{r['id']}/cancel").json()["status"] == "done"   # finished goals are not touched


def test_a_lease_held_by_a_dead_process_on_this_host_is_void_at_once():
    import socket
    g = Goal(user_id="w8", text="x"); g.status = GoalStatus.RUNNING; store.save_goal(g)
    store.claim_lease(g.id, f"{socket.gethostname()}:999999", (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat())   # no such pid
    assert worker.resume_interrupted(_llm("Back.")) == [g.id] and worker.wait(g.id).summary == "Back."
    assert store.purge_lapsed_leases() == 0 and worker.state()["leases"] == []
