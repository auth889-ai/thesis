"""The agent's vocabulary: a Goal becomes a Plan of Steps; a Step is a ToolCall or a Question; every ToolCall
carries a RiskClass that the permission engine decides on BEFORE execution; every decision and result is an
AuditEntry. Plain dataclasses: they are stored as JSON and shown to the user as they are."""
from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class RiskClass(str, enum.Enum):
    """What a tool call can do to the world. The permission engine maps each class to a policy."""
    READ = "read"                              # looks at data the user already has (forecast, calendar view)
    WRITE_REVERSIBLE = "write_reversible"      # creates/edits something the user can undo (a task, a draft, a saved commute)
    WRITE_IRREVERSIBLE = "write_irreversible"  # cannot be undone by the app (delete, mark done, cancel)
    EXTERNAL = "external"                      # leaves the user's own space (send an email, post, book)
    FINANCIAL = "financial"                    # money moves


class Decision(str, enum.Enum):
    ALLOW = "allow"                 # executed without asking
    ASK = "ask"                     # paused until the user approves this exact call
    REFUSE = "refuse"               # never executed; the reason is shown


class GoalStatus(str, enum.Enum):
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_USER = "waiting_user"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("call"))
    risk: RiskClass = RiskClass.READ
    decision: Decision | None = None
    decision_reason: str | None = None
    result: Any = None
    error: str | None = None
    started_utc: str | None = None
    finished_utc: str | None = None


@dataclass
class Step:
    """One unit of a plan: the model's stated intent and the call it chose (or a question for the user)."""
    thought: str
    call: ToolCall | None = None
    question: str | None = None
    answer: str | None = None
    id: str = field(default_factory=lambda: new_id("step"))
    created_utc: str = field(default_factory=now_iso)


@dataclass
class Goal:
    user_id: str
    text: str
    id: str = field(default_factory=lambda: new_id("goal"))
    status: GoalStatus = GoalStatus.PLANNING
    steps: list[Step] = field(default_factory=list)
    summary: str | None = None
    model: str | None = None
    created_utc: str = field(default_factory=now_iso)
    updated_utc: str = field(default_factory=now_iso)
    tokens_in: int = 0
    tokens_out: int = 0
    intent: dict | None = None                # what the person wants, recorded before planning (agent/intent.py)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEntry:
    """Append-only. Written BEFORE a call executes (decision) and again after (result)."""
    user_id: str
    goal_id: str
    kind: str                       # decision | result | question | answer | approval | refusal | error | summary
    detail: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("audit"))
    at_utc: str = field(default_factory=now_iso)
