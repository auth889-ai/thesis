"""Agent routes: submit a goal, follow it, approve a paused action, answer a question, read the audit log."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.agent import approvals, audit, intent, memory, orchestrator, store, tools, worker, you
from app.agent.models import AuditEntry, Goal, GoalStatus
from app.agent.schemas import AnswerRequest, ApproveRequest, GoalRequest, StartRequest, RuleRequest

router = APIRouter()


@lru_cache(maxsize=1)
def _llm():
    from app.agent.llm import Bedrock
    return Bedrock()


def _llm_or_503():
    try:
        return _llm()
    except Exception as exc:                                        # noqa: BLE001 - the page shows the real reason
        raise HTTPException(503, f"language model unavailable: {type(exc).__name__}: {str(exc)[:200]}")


@router.post("/api/agent/goals", status_code=202, tags=["agent"])
def submit_goal(req: GoalRequest):
    """Run the goal until it finishes or pauses (approval needed, or a question for the user)."""
    llm = _llm_or_503()
    goal = Goal(user_id=req.user_id, text=req.text, intent=intent.extract(req.text, llm, req.user_id)); store.save_goal(goal)
    audit.write(AuditEntry(user_id=goal.user_id, goal_id=goal.id, kind="intent", detail=goal.intent))
    if not req.start:
        goal.status = GoalStatus.PROPOSED; store.save_goal(goal)
        return goal.to_dict()
    return _launch(goal)


def _launch(goal: Goal) -> dict:
    """Mark the goal running and hand it to the worker; the page polls GET /api/agent/goals/{id}."""
    goal.status = GoalStatus.RUNNING; store.save_goal(goal)
    if not worker.enqueue(goal.id, _llm_or_503):
        raise HTTPException(409, "this goal is already being worked on")
    return goal.to_dict()


@router.post("/api/agent/goals/{goal_id}/start", tags=["agent"])
def start_goal(goal_id: str, req: StartRequest | None = None):
    """Start a proposed goal; with an edited text the intent is read again first."""
    g = store.load_goal(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    if g.status != GoalStatus.PROPOSED:
        raise HTTPException(409, f"goal is {g.status.value}, not proposed")
    llm = _llm_or_503()
    if req and req.text and req.text.strip() and req.text.strip() != g.text:
        g.text = req.text.strip(); g.intent = intent.extract(g.text, llm, g.user_id)
        audit.write(AuditEntry(user_id=g.user_id, goal_id=g.id, kind="intent", detail=g.intent))
    audit.write(AuditEntry(user_id=g.user_id, goal_id=g.id, kind="start", detail={"text": g.text}))
    return _launch(g)


@router.post("/api/agent/goals/{goal_id}/cancel", tags=["agent"])
def cancel_goal(goal_id: str):
    """Stop a goal: at once when it is waiting for you, at its next step when it is running."""
    g = worker.cancel(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    return g.to_dict()


@router.get("/api/agent/worker", tags=["agent"])
def worker_state():
    return worker.state()


@router.get("/api/agent/goals", tags=["agent"])
def list_goals(user_id: str = "demo"):
    return {"user_id": user_id, "goals": store.list_goals(user_id)}


@router.get("/api/agent/goals/{goal_id}", tags=["agent"])
def get_goal(goal_id: str):
    g = store.load_goal(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    return g.to_dict()


@router.post("/api/agent/goals/{goal_id}/approve", tags=["agent"])
def approve(goal_id: str, req: ApproveRequest):
    g = store.load_goal(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    try:
        g = orchestrator.approve(g, req.call_id, req.approved, _llm_or_503(), message=req.message, always=req.always, action_hash=req.action_hash, resume=False)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return _launch(g)


@router.post("/api/agent/goals/{goal_id}/answer", tags=["agent"])
def answer(goal_id: str, req: AnswerRequest):
    g = store.load_goal(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    try:
        g = orchestrator.answer(g, req.step_id, req.text, _llm_or_503(), resume=False)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return _launch(g)


@router.get("/api/agent/approvals/rules", tags=["agent"])
def approval_rules(user_id: str = "demo"):
    """The person's standing decisions: tools they allow or decline every time, with when they said so."""
    return {"user_id": user_id, "rules": approvals.list_rules(user_id)}


@router.post("/api/agent/approvals/rules", tags=["agent"])
def set_approval_rule(req: RuleRequest):
    return approvals.set_rule(req.user_id, req.tool, req.decision, None)


@router.delete("/api/agent/approvals/rules/{tool}", tags=["agent"])
def clear_approval_rule(tool: str, user_id: str = "demo"):
    if not approvals.clear_rule(user_id, tool):
        raise HTTPException(404, "no such rule")
    return {"cleared": tool}


@router.get("/api/agent/audit", tags=["agent"])
def audit_log(user_id: str = "demo", goal_id: str | None = None, limit: int = 200):
    return {"user_id": user_id, "entries": audit.read(user_id, goal_id, limit), "chain": audit.verify(user_id)}


@router.get("/api/agent/tools", tags=["agent"])
def tool_list():
    return {"tools": [{"name": t.name, "description": t.description, "risk": t.risk.value, "schema": t.schema} for t in tools.TOOLS.values()], "policy": {k.value: v.value for k, v in __import__("app.agent.permissions", fromlist=["POLICY"]).POLICY.items()}}


@router.get("/api/agent/tasks", tags=["agent"])
def tasks(user_id: str = "demo"):
    return {"tasks": store.list_tasks(user_id, None), "reminders": store.list_reminders(user_id, None), "commutes": store.list_commutes(user_id)}


@router.get("/api/agent/goals/{goal_id}/related", tags=["agent"])
def goal_related(goal_id: str):
    """What the goal created: tasks and reminders that name it as their source."""
    g = store.load_goal(goal_id)
    if not g:
        raise HTTPException(404, "no such goal")
    return {"goal_id": goal_id} | store.items_for_goal(g.user_id, goal_id)


@router.get("/api/agent/memory", tags=["agent"])
def memory_list(user_id: str = "demo"):
    """What the assistant keeps about the person: preferences, places, patterns, constraints — each with its origin."""
    return {"user_id": user_id, "facts": memory.list_all(user_id), "kinds": list(memory.KINDS)}


@router.delete("/api/agent/memory/{fact_id}", tags=["agent"])
def memory_forget(fact_id: str, user_id: str = "demo"):
    if not memory.forget(user_id, fact_id):
        raise HTTPException(404, "no such fact")
    return {"forgotten": fact_id}


@router.get("/api/you/export", tags=["you"])
def you_export(user_id: str = "demo"):
    """Everything held about the person, as one document."""
    return you.export(user_id)


@router.delete("/api/you", tags=["you"])
def you_erase(user_id: str = "demo", confirm: str = ""):
    """Erase everything held about the person. `confirm` must equal the user id: a browser cannot do this by accident."""
    if confirm != user_id:
        raise HTTPException(400, "pass confirm=<your user id> to erase")
    return you.erase(user_id)
