"""One row per person. Created on first save; read by every module that needs the person's city, clock or places."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from app.paths import REPO

DB = REPO / "results/live/agent/profiles.sqlite"
_LOCK = threading.Lock()
FIELDS = ("user_id", "name", "timezone", "city", "lat", "lng", "home", "work", "on_time_target", "created_utc", "updated_utc")


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists profiles (user_id text primary key, name text, timezone text, city text, lat real, lng real, home text, work text, on_time_target real, created_utc text, updated_utc text)")
    return c


def get(user_id: str) -> dict | None:
    with _conn() as c:
        r = c.execute("select * from profiles where user_id=?", (user_id,)).fetchone()
    return dict(r) if r else None


def save(user_id: str, **fields) -> dict:
    """Merge the given fields into the person's row; unknown keys are ignored, missing ones kept."""
    now = datetime.now(timezone.utc).isoformat()
    cur = get(user_id) or {k: None for k in FIELDS} | {"user_id": user_id, "created_utc": now}
    row = {**cur, **{k: v for k, v in fields.items() if k in FIELDS and k not in ("user_id", "created_utc")}, "updated_utc": now}
    with _LOCK, _conn() as c:
        c.execute(f"insert or replace into profiles ({','.join(FIELDS)}) values ({','.join('?' * len(FIELDS))})", tuple(row[k] for k in FIELDS))
    return row


def erase_user(user_id: str) -> int:
    with _LOCK, _conn() as c:
        return c.execute("delete from profiles where user_id=?", (user_id,)).rowcount
