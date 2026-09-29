"""APPROVALS — an approval is bound to one exact action, it expires, and the person can turn it into a rule.

Two open implementations were read and their design taken over, adapted to our permission engine:
  - OpenMuse (tahodev/openmuse @ e39abd6, docs/architecture): "exact-action approval" — a sensitive call is
    approved as the hash of (tool, arguments) computed when it was proposed, once, inside a time window; if the
    arguments change the approval is void; the planner cannot mint an approval itself.
  - OpenAI Agents SDK (openai/openai-agents-python @ 7b27134, docs/human_in_the_loop.md): a tool declares
    `needs_approval` as a flag or a predicate over the arguments; the person may `always_approve` /
    `always_reject` a tool; a rejection carries a `rejection_message` the model reads and replans from.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.agent import store
from app.agent.models import ToolCall

TTL_MIN = 30                                    # a proposed action must be approved within this window
RULES = ("approve", "reject")


def action_hash(tool: str, arguments: dict) -> str:
    """The identity of one exact action: the tool and its arguments, canonically serialised."""
    return hashlib.sha256(json.dumps({"tool": tool, "arguments": arguments}, sort_keys=True, default=str).encode()).hexdigest()[:16]


def bind(call: ToolCall, now: datetime | None = None) -> None:
    """Stamp a paused call with its hash and expiry; the app shows both and sends the hash back with the decision."""
    now = now or datetime.now(timezone.utc)
    call.action_hash = action_hash(call.tool, call.arguments)
    call.approval_expires_utc = (now + timedelta(minutes=TTL_MIN)).isoformat()


def expired(call: ToolCall, now: datetime | None = None) -> bool:
    if not call.approval_expires_utc:
        return False
    return (now or datetime.now(timezone.utc)) >= datetime.fromisoformat(call.approval_expires_utc)


def check(call: ToolCall, presented_hash: str | None) -> str | None:
    """Why this approval cannot be accepted, or None. The hash the person saw must be the hash of the call as
    it is now; an approval given for different arguments is not an approval of these."""
    if expired(call):
        return f"this approval expired after {TTL_MIN} minutes; the assistant will propose the action again"
    if presented_hash and call.action_hash and presented_hash != call.action_hash:
        return "the action changed since you saw it; look at it again before approving"
    return None


def rule_for(user_id: str, tool: str) -> dict | None:
    return store.get_approval_rule(user_id, tool)


def set_rule(user_id: str, tool: str, decision: str, source_goal: str | None) -> dict:
    if decision not in RULES:
        raise ValueError(f"decision must be one of {RULES}")
    return store.set_approval_rule(user_id, tool, decision, source_goal)


def clear_rule(user_id: str, tool: str) -> bool:
    return store.clear_approval_rule(user_id, tool)


def list_rules(user_id: str) -> list[dict]:
    return store.list_approval_rules(user_id)
