"""THE ORCHESTRATOR — the ReAct loop (Yao et al., ICLR 2023) with a permission engine in front of every action.

    goal → [model: thought + tool call] → permission decision (logged) → execute (logged) → observation → …
                                        ↘ ASK  → goal pauses (WAITING_APPROVAL) until the user approves this exact call
                                        ↘ user.ask → goal pauses (WAITING_USER) until the user answers
    … → model ends the turn with text → summary, DONE

Nothing is executed without a logged decision; the model never sees invented tool results; when a required
detail is missing the model must ask (user.ask), not guess. A goal is a durable object (store.py): the loop can
stop at any step and be resumed later with the same context.
"""
from __future__ import annotations

import json
from typing import Any

from app.agent import audit, memory, permissions, store, tools
from app.agent.models import AuditEntry, Decision, Goal, GoalStatus, Step, ToolCall, now_iso

MAX_STEPS = 12
SYSTEM = """You are TrafficTwin's assistant. You complete the user's goal by calling tools; you never invent facts, times or
personal details. If a detail you need (a place, a time, a recipient) is neither in the goal nor in a tool result,
call user__ask with one specific question instead of guessing. Times are local Dhaka time (+06:00) written as
YYYY-MM-DDTHH:MM. When the goal is complete, reply with a short plain summary of what you did and what the user
should know (including any honesty labels the tools returned, such as 'recorded, not live'). When the person states a durable
preference, place or constraint, keep it with memory__remember. Today is {today}.
{memory}"""


def _context_text(goal: Goal) -> str:
    """Everything the model may legitimately know: the goal, the user's answers and every tool result."""
    parts = [goal.text]
    for s in goal.steps:
        if s.answer:
            parts.append(s.answer)
        if s.call and s.call.result is not None:
            parts.append(json.dumps(s.call.result, default=str))
    return "\n".join(parts)


def _messages(goal: Goal) -> list[dict]:
    """Rebuild the conversation from the durable goal record (so a resumed goal continues with full context)."""
    msgs = [{"role": "user", "content": [{"text": goal.text}]}]
    for s in goal.steps:
        if s.call:
            msgs.append({"role": "assistant", "content": ([{"text": s.thought}] if s.thought else []) + [{"toolUse": {"toolUseId": s.call.id, "name": s.call.tool.replace(".", "__"), "input": s.call.arguments}}]})
            if s.call.result is not None or s.call.error or s.call.decision in (Decision.REFUSE,):
                body = s.call.result if s.call.result is not None else {"error": s.call.error or s.call.decision_reason}
                msgs.append({"role": "user", "content": [{"toolResult": {"toolUseId": s.call.id, "content": [{"json": body if isinstance(body, dict) else {"result": body}}]}}]})
            else:
                return msgs                                        # pending approval: the conversation stops here
        elif s.question:
            msgs.append({"role": "assistant", "content": [{"text": s.thought}] + [{"toolUse": {"toolUseId": s.id, "name": "user__ask", "input": {"question": s.question}}}]})
            if s.answer:
                msgs.append({"role": "user", "content": [{"toolResult": {"toolUseId": s.id, "content": [{"json": {"answer": s.answer}}]}}]})
            else:
                return msgs
        elif s.thought:
            msgs.append({"role": "assistant", "content": [{"text": s.thought}]})
    return msgs


def _log(goal: Goal, kind: str, detail: dict) -> None:
    audit.write(AuditEntry(user_id=goal.user_id, goal_id=goal.id, kind=kind, detail=detail))


def _execute(goal: Goal, step: Step) -> None:
    call = step.call; tool = tools.TOOLS[call.tool]
    call.started_utc = now_iso()
    try:
        call.result = tool.handler(goal.user_id, call.arguments, goal.id)
    except Exception as exc:                                       # noqa: BLE001 - the model sees the real error, the log keeps it
        call.error = f"{type(exc).__name__}: {exc}"
    call.finished_utc = now_iso()
    _log(goal, "result", {"call_id": call.id, "tool": call.tool, "ok": call.error is None, "error": call.error, "result_preview": str(call.result)[:400]})


def run(goal: Goal, llm, max_steps: int = MAX_STEPS) -> Goal:
    """Advance the goal until it is done, paused (approval / question) or failed. Safe to call again to resume."""
    from datetime import datetime, timedelta, timezone
    today = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime("%Y-%m-%d (%A)")
    goal.model = getattr(llm, "model", None); goal.status = GoalStatus.RUNNING; store.save_goal(goal)
    for _ in range(max_steps):
        pending = next((s for s in goal.steps if s.call and s.call.decision == Decision.ASK and s.call.result is None and s.call.error is None), None)
        if pending:
            goal.status = GoalStatus.WAITING_APPROVAL; store.save_goal(goal); return goal
        unanswered = next((s for s in goal.steps if s.question and not s.answer), None)
        if unanswered:
            goal.status = GoalStatus.WAITING_USER; store.save_goal(goal); return goal
        turn = llm.complete(SYSTEM.format(today=today, memory=memory.prompt_section(goal.user_id, goal.text)), _messages(goal), tools.tool_specs())
        goal.tokens_in += turn.tokens_in; goal.tokens_out += turn.tokens_out
        if not turn.tool_calls:
            goal.summary = turn.text or "(done)"; goal.status = GoalStatus.DONE
            goal.steps.append(Step(thought=turn.text)); _log(goal, "summary", {"text": goal.summary, "tokens_in": goal.tokens_in, "tokens_out": goal.tokens_out}); store.save_goal(goal); return goal
        for tc in turn.tool_calls:
            name = tools.resolve(tc["name"])
            if name == tools.ASK_USER:
                step = Step(thought=turn.text, question=tc["input"].get("question", "?")); step.id = tc["id"]; goal.steps.append(step)
                _log(goal, "question", {"question": step.question}); goal.status = GoalStatus.WAITING_USER; store.save_goal(goal); return goal
            if name not in tools.TOOLS:
                call = ToolCall(tool=name, arguments=tc["input"], id=tc["id"]); call.error = f"unknown tool {name}"; call.decision = Decision.REFUSE; call.decision_reason = "no such tool"
                goal.steps.append(Step(thought=turn.text, call=call)); _log(goal, "refusal", {"tool": name, "reason": "no such tool"}); continue
            tool = tools.TOOLS[name]
            call = ToolCall(tool=name, arguments=tc["input"], id=tc["id"], risk=tool.risk)
            call.decision, call.decision_reason = permissions.decide(call, tool.risk, _context_text(goal))
            step = Step(thought=turn.text, call=call); goal.steps.append(step)
            _log(goal, "decision", {"call_id": call.id, "tool": name, "arguments": call.arguments, "risk": tool.risk.value, "decision": call.decision.value, "reason": call.decision_reason})
            if call.decision == Decision.ALLOW:
                _execute(goal, step)
            elif call.decision == Decision.REFUSE:
                call.error = f"refused: {call.decision_reason}"
            else:
                goal.status = GoalStatus.WAITING_APPROVAL; store.save_goal(goal); return goal
        store.save_goal(goal)
    goal.status = GoalStatus.FAILED; goal.summary = f"stopped after {max_steps} steps without finishing"; _log(goal, "error", {"reason": goal.summary}); store.save_goal(goal); return goal


def approve(goal: Goal, call_id: str, approved: bool, llm) -> Goal:
    step = next((s for s in goal.steps if s.call and s.call.id == call_id), None)
    if not step or step.call.decision != Decision.ASK or step.call.result is not None:
        raise ValueError("no pending approval with that id")
    _log(goal, "approval", {"call_id": call_id, "tool": step.call.tool, "arguments": step.call.arguments, "approved": approved})
    if approved:
        _execute(goal, step)
    else:
        step.call.error = "declined by the user"
    return run(goal, llm)


def answer(goal: Goal, step_id: str, text: str, llm) -> Goal:
    step = next((s for s in goal.steps if s.id == step_id and s.question), None)
    if not step or step.answer:
        raise ValueError("no open question with that id")
    step.answer = text; _log(goal, "answer", {"step_id": step_id, "answer": text})
    return run(goal, llm)
