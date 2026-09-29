"""What the assistant remembers about a person: durable preferences, places and patterns, never a transcript.

    remember(user, text, kind)      a fact the model or the person chose to keep ("prefers reliability over speed")
    recall(user, goal_text)         the facts most relevant to a goal, recent first, for the planner's prompt
    forget(user, fact_id)           gone for good (an irreversible tool: the planner asks first)

Facts are short sentences with a kind (preference · place · pattern · constraint) and the goal that produced them.
Retrieval is lexical overlap plus recency (the Generative Agents recipe without the importance score); a fact
is shown to the model as text it may use, never as an instruction.
"""
from __future__ import annotations

import re
import sqlite3

from app.agent.models import RiskClass, new_id, now_iso
from app.agent.store import DB, _LOCK

KINDS = ("preference", "place", "pattern", "constraint")
MAX_FACTS_IN_PROMPT = 8


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists memories (id text primary key, user_id text, kind text, text text, created_utc text, source_goal text, uses integer default 0)")
    return c


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (s or "").lower())}


def remember(user_id: str, text: str, kind: str = "preference", source_goal: str | None = None) -> dict:
    kind = kind if kind in KINDS else "preference"
    text = " ".join((text or "").split())[:240]
    if not text:
        raise ValueError("nothing to remember")
    with _LOCK, _conn() as c:
        dup = c.execute("select * from memories where user_id=? and lower(text)=lower(?)", (user_id, text)).fetchone()
        if dup:
            return dict(dup)
        row = {"id": new_id("mem"), "user_id": user_id, "kind": kind, "text": text, "created_utc": now_iso(), "source_goal": source_goal, "uses": 0}
        c.execute("insert into memories values (?,?,?,?,?,?,?)", tuple(row.values()))
    return row


def list_all(user_id: str) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from memories where user_id=? order by created_utc desc", (user_id,)).fetchall()]


def forget(user_id: str, fact_id: str) -> bool:
    with _LOCK, _conn() as c:
        return c.execute("delete from memories where id=? and user_id=?", (fact_id, user_id)).rowcount > 0


def recall(user_id: str, goal_text: str, limit: int = MAX_FACTS_IN_PROMPT) -> list[dict]:
    """The facts worth showing for this goal: lexical overlap first, then recency; constraints always."""
    facts = list_all(user_id)
    if not facts:
        return []
    q = _tokens(goal_text)
    scored = sorted(facts, key=lambda f: (f["kind"] == "constraint", len(q & _tokens(f["text"])), f["created_utc"]), reverse=True)
    chosen = scored[:limit]
    with _LOCK, _conn() as c:
        c.executemany("update memories set uses=uses+1 where id=?", [(f["id"],) for f in chosen])
    return chosen


def prompt_section(user_id: str, goal_text: str) -> str:
    facts = recall(user_id, goal_text)
    if not facts:
        return ""
    return "What you know about this person (facts they chose to keep; use them, do not repeat them back):\n" + "\n".join(f"- [{f['kind']}] {f['text']}" for f in facts)


# ------------------------------------------------------------------ tool handlers (user_id, arguments, goal_id)
def tool_remember(user_id, a, goal_id):
    return remember(user_id, a["text"], a.get("kind", "preference"), goal_id)


def tool_list(user_id, a, goal_id):
    return {"memories": list_all(user_id)}


def tool_forget(user_id, a, goal_id):
    return {"forgotten": forget(user_id, a["memory_id"])}


TOOL_SPECS = [
    ("memory.remember", "Keep a durable fact about the person for future plans: a preference, a usual place, a recurring pattern or a constraint. Only facts the person stated or clearly implied.", {"type": "object", "properties": {"text": {"type": "string"}, "kind": {"type": "string", "enum": list(KINDS), "default": "preference"}}, "required": ["text"]}, RiskClass.WRITE_REVERSIBLE, tool_remember),
    ("memory.list", "List what is remembered about the person.", {"type": "object", "properties": {}, "required": []}, RiskClass.READ, tool_list),
    ("memory.forget", "Forget one remembered fact for good.", {"type": "object", "properties": {"memory_id": {"type": "string"}}, "required": ["memory_id"]}, RiskClass.WRITE_IRREVERSIBLE, tool_forget),
]


def erase_user(user_id: str) -> int:
    with _LOCK, _conn() as c:
        return c.execute("delete from memories where user_id=?", (user_id,)).rowcount
