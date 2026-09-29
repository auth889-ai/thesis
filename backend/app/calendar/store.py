"""The events table: imported events keep their calendar UID so a re-import updates rather than duplicates."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.agent.models import new_id, now_iso
from app.agent.store import DB, _LOCK


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.executescript("""
        create table if not exists events (id text primary key, user_id text, uid text, title text, start_utc text, end_utc text, location text, all_day integer,
                                           description text, source text, created_utc text, updated_utc text);
        create unique index if not exists events_uid on events(user_id, uid);
        create table if not exists calendars (id text primary key, user_id text, url text, name text, imported_utc text, events integer);
    """)
    return c


def upsert(user_id: str, ev: dict, source: str) -> dict:
    row = {"id": new_id("ev"), "user_id": user_id, "uid": ev["uid"], "title": ev["title"], "start_utc": ev["start_utc"], "end_utc": ev.get("end_utc") or ev["start_utc"],
           "location": ev.get("location") or "", "all_day": 1 if ev.get("all_day") else 0, "description": ev.get("description") or "", "source": source, "created_utc": now_iso(), "updated_utc": now_iso()}
    with _LOCK, _conn() as c:
        old = c.execute("select id, created_utc from events where user_id=? and uid=?", (user_id, ev["uid"])).fetchone()
        if old:
            row["id"], row["created_utc"] = old["id"], old["created_utc"]
        c.execute("insert or replace into events values (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
    return row


def import_events(user_id: str, events: list[dict], source: str) -> list[dict]:
    return [upsert(user_id, e, source) for e in events]


def remember_calendar(user_id: str, url: str, name: str, n: int) -> dict:
    row = {"id": new_id("cal"), "user_id": user_id, "url": url, "name": name, "imported_utc": now_iso(), "events": n}
    with _LOCK, _conn() as c:
        c.execute("delete from calendars where user_id=? and url=?", (user_id, url))
        c.execute("insert into calendars values (?,?,?,?,?,?)", tuple(row.values()))
    return row


def list_calendars(user_id: str) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from calendars where user_id=? order by imported_utc desc", (user_id,)).fetchall()]


def upcoming(user_id: str, hours: float = 36.0, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    lo, hi = (now - timedelta(hours=1)).isoformat(), (now + timedelta(hours=hours)).isoformat()
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from events where user_id=? and start_utc between ? and ? order by start_utc", (user_id, lo, hi)).fetchall()]


def between(user_id: str, start_utc: str, end_utc: str) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from events where user_id=? and start_utc >= ? and start_utc < ? order by start_utc", (user_id, start_utc, end_utc)).fetchall()]


def erase_user(user_id: str) -> dict:
    with _LOCK, _conn() as c:
        return {t: c.execute(f"delete from {t} where user_id=?", (user_id,)).rowcount for t in ("events", "calendars")}
