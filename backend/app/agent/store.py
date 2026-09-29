"""Per-user storage for the agent: goals (with their steps), tasks and reminders. SQLite, one file, created on
first use. Goals are stored as JSON documents (the dataclasses in models.py); tasks and reminders are rows the
tools read and write — the only 'world' the agent can change in this build, and every change is reversible
through the same tools."""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import datetime, timezone

from app.agent.models import Decision, Goal, GoalStatus, RiskClass, Step, ToolCall, now_iso, new_id
from app.paths import REPO

DB = REPO / "results/live/agent/agent.sqlite"
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.executescript("""
        create table if not exists goals (id text primary key, user_id text, status text, updated_utc text, doc text);
        create table if not exists tasks (id text primary key, user_id text, title text, due_utc text, status text, created_utc text, updated_utc text, source_goal text);
        create table if not exists reminders (id text primary key, user_id text, text text, at_utc text, status text, created_utc text, source_goal text);
        create table if not exists commutes (id text primary key, user_id text, name text, origin text, destination text, arrive_by_local text, created_utc text);
        create table if not exists approval_rules (user_id text, tool text, decision text, created_utc text, source_goal text, primary key (user_id, tool));
        create table if not exists goal_leases (goal_id text primary key, lease_id text, worker text, until_utc text, claimed_utc text);
        create table if not exists goal_control (goal_id text primary key, cancel_requested_utc text);
        create index if not exists goals_user on goals(user_id, updated_utc);
    """)
    return c


# ------------------------------------------------------------------ goals
def _goal_from_doc(d: dict) -> Goal:
    steps = []
    for s in d.get("steps", []):
        c = s.get("call"); call = None
        if c:
            call = ToolCall(**{**c, "risk": RiskClass(c["risk"]), "decision": Decision(c["decision"]) if c.get("decision") else None})
        steps.append(Step(thought=s["thought"], call=call, question=s.get("question"), answer=s.get("answer"), id=s["id"], created_utc=s["created_utc"]))
    return Goal(user_id=d["user_id"], text=d["text"], id=d["id"], status=GoalStatus(d["status"]), steps=steps, summary=d.get("summary"), model=d.get("model"), created_utc=d["created_utc"], updated_utc=d["updated_utc"], tokens_in=d.get("tokens_in", 0), tokens_out=d.get("tokens_out", 0), intent=d.get("intent"))


def save_goal(g: Goal) -> None:
    g.updated_utc = now_iso()
    with _LOCK, _conn() as c:
        c.execute("insert or replace into goals (id, user_id, status, updated_utc, doc) values (?,?,?,?,?)", (g.id, g.user_id, g.status.value, g.updated_utc, json.dumps(asdict(g), default=str)))


def load_goal(goal_id: str) -> Goal | None:
    with _conn() as c:
        r = c.execute("select doc from goals where id=?", (goal_id,)).fetchone()
    return _goal_from_doc(json.loads(r["doc"])) if r else None


def list_goals(user_id: str, limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute("select doc from goals where user_id=? order by updated_utc desc limit ?", (user_id, limit)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["doc"]); out.append({k: d[k] for k in ("id", "text", "status", "summary", "created_utc", "updated_utc")} | {"steps": len(d.get("steps", [])), "intent": d.get("intent")})
    return out


# ------------------------------------------------------------------ tasks & reminders (the tools' world)
def create_task(user_id: str, title: str, due_utc: str | None, source_goal: str | None) -> dict:
    t = {"id": new_id("task"), "user_id": user_id, "title": title, "due_utc": due_utc, "status": "open", "created_utc": now_iso(), "updated_utc": now_iso(), "source_goal": source_goal}
    with _LOCK, _conn() as c:
        c.execute("insert into tasks values (?,?,?,?,?,?,?,?)", tuple(t.values()))
    return t


def list_tasks(user_id: str, status: str | None = "open") -> list[dict]:
    with _conn() as c:
        q = "select * from tasks where user_id=?" + (" and status=?" if status else "") + " order by coalesce(due_utc, '9999') asc"
        return [dict(r) for r in c.execute(q, (user_id, status) if status else (user_id,)).fetchall()]


def set_task_status(user_id: str, task_id: str, status: str) -> dict | None:
    with _LOCK, _conn() as c:
        c.execute("update tasks set status=?, updated_utc=? where id=? and user_id=?", (status, now_iso(), task_id, user_id))
        r = c.execute("select * from tasks where id=? and user_id=?", (task_id, user_id)).fetchone()
    return dict(r) if r else None


def create_reminder(user_id: str, text: str, at_utc: str, source_goal: str | None) -> dict:
    r = {"id": new_id("rem"), "user_id": user_id, "text": text, "at_utc": at_utc, "status": "scheduled", "created_utc": now_iso(), "source_goal": source_goal}
    with _LOCK, _conn() as c:
        c.execute("insert into reminders values (?,?,?,?,?,?,?)", tuple(r.values()))
    return r


def list_reminders(user_id: str, status: str | None = "scheduled") -> list[dict]:
    with _conn() as c:
        q = "select * from reminders where user_id=?" + (" and status=?" if status else "") + " order by at_utc asc"
        return [dict(r) for r in c.execute(q, (user_id, status) if status else (user_id,)).fetchall()]


def due_reminders(now_utc: str | None = None) -> list[dict]:
    now_utc = now_utc or now_iso()
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from reminders where status='scheduled' and at_utc<=? order by at_utc", (now_utc,)).fetchall()]


def save_commute(user_id: str, name: str, origin: str, destination: str, arrive_by_local: str) -> dict:
    r = {"id": new_id("cmt"), "user_id": user_id, "name": name, "origin": origin, "destination": destination, "arrive_by_local": arrive_by_local, "created_utc": now_iso()}
    with _LOCK, _conn() as c:
        c.execute("insert into commutes values (?,?,?,?,?,?,?)", tuple(r.values()))
    return r


def list_commutes(user_id: str) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from commutes where user_id=? order by created_utc", (user_id,)).fetchall()]


# ------------------------------------------------------------------ standing approval rules (agent/approvals.py)
def set_approval_rule(user_id: str, tool: str, decision: str, source_goal: str | None) -> dict:
    row = {"user_id": user_id, "tool": tool, "decision": decision, "created_utc": now_iso(), "source_goal": source_goal}
    with _LOCK, _conn() as c:
        c.execute("insert or replace into approval_rules values (?,?,?,?,?)", tuple(row.values()))
    return row


def get_approval_rule(user_id: str, tool: str) -> dict | None:
    with _conn() as c:
        r = c.execute("select * from approval_rules where user_id=? and tool=?", (user_id, tool)).fetchone()
    return dict(r) if r else None


def list_approval_rules(user_id: str) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from approval_rules where user_id=? order by created_utc desc", (user_id,)).fetchall()]


def clear_approval_rule(user_id: str, tool: str) -> bool:
    with _LOCK, _conn() as c:
        return c.execute("delete from approval_rules where user_id=? and tool=?", (user_id, tool)).rowcount > 0


# ------------------------------------------------------------------ leases and cancel flags (agent/worker.py)
def claim_lease(goal_id: str, worker: str, until_utc: str) -> str | None:
    """One runner per goal: the claim succeeds when no lease exists or the existing one has lapsed."""
    lease_id = new_id("lease")
    with _LOCK, _conn() as c:
        row = c.execute("select until_utc from goal_leases where goal_id=?", (goal_id,)).fetchone()
        if row and row["until_utc"] > now_iso():
            return None
        c.execute("insert or replace into goal_leases values (?,?,?,?,?)", (goal_id, lease_id, worker, until_utc, now_iso()))
    return lease_id


def renew_lease(goal_id: str, lease_id: str, until_utc: str) -> bool:
    with _LOCK, _conn() as c:
        return c.execute("update goal_leases set until_utc=? where goal_id=? and lease_id=?", (until_utc, goal_id, lease_id)).rowcount == 1


def release_lease(goal_id: str, lease_id: str) -> None:
    with _LOCK, _conn() as c:
        c.execute("delete from goal_leases where goal_id=? and lease_id=?", (goal_id, lease_id))


def lease_holder(goal_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("select * from goal_leases where goal_id=?", (goal_id,)).fetchone()
    return dict(row) if row else None


def purge_lapsed_leases() -> int:
    with _LOCK, _conn() as c:
        return c.execute("delete from goal_leases where until_utc <= ?", (now_iso(),)).rowcount


def lease_alive(goal_id: str) -> bool:
    with _conn() as c:
        row = c.execute("select until_utc from goal_leases where goal_id=?", (goal_id,)).fetchone()
    return bool(row and row["until_utc"] > now_iso())


def list_leases() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from goal_leases order by claimed_utc").fetchall()]


def active_goals(statuses: tuple[str, ...]) -> list[str]:
    with _conn() as c:
        return [r["id"] for r in c.execute(f"select id from goals where status in ({','.join('?' * len(statuses))}) order by updated_utc", statuses).fetchall()]


def request_cancel(goal_id: str) -> None:
    with _LOCK, _conn() as c:
        c.execute("insert or replace into goal_control values (?,?)", (goal_id, now_iso()))


def cancel_requested(goal_id: str) -> bool:
    with _conn() as c:
        return c.execute("select 1 from goal_control where goal_id=?", (goal_id,)).fetchone() is not None


# ------------------------------------------------------------------ erasure (agent/you.py)
def erase_user(user_id: str) -> dict:
    """Delete every row of this person's in the agent store; returns what was removed per table."""
    out = {}
    with _LOCK, _conn() as c:
        ids = [r["id"] for r in c.execute("select id from goals where user_id=?", (user_id,)).fetchall()]
        for table in ("goals", "tasks", "reminders", "commutes", "approval_rules"):
            out[table] = c.execute(f"delete from {table} where user_id=?", (user_id,)).rowcount
        for table in ("goal_leases", "goal_control"):
            out[table] = sum(c.execute(f"delete from {table} where goal_id=?", (g,)).rowcount for g in ids)
    return out


def items_for_goal(user_id: str, goal_id: str) -> dict:
    """What a goal created: its tasks and reminders (the tools record the goal that made them)."""
    with _conn() as c:
        return {"tasks": [dict(r) for r in c.execute("select * from tasks where user_id=? and source_goal=? order by created_utc", (user_id, goal_id)).fetchall()],
                "reminders": [dict(r) for r in c.execute("select * from reminders where user_id=? and source_goal=? order by at_utc", (user_id, goal_id)).fetchall()]}
