"""The watch on the person's day: every few minutes, every upcoming departure is recomputed from the current
state of the roads; when the recommended departure moves or the on-time probability drops, the person is told
why. The last recommendation per departure is kept only to detect the change; the plan itself is always fresh."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone

from app.agent import store as agent_store
from app.agent.models import now_iso
from app.agent.store import DB, _LOCK
from app.plan import day, notifications

TICK_S = 300
MOVE_MIN = 5                 # a departure that moves by this many minutes is worth a message
PROB_DROP = 0.15             # or an on-time probability that falls by this much
_thread: threading.Thread | None = None
_state = {"ticks": 0, "last_tick_utc": None, "last_error": None, "changes": 0}


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists watch (user_id text, ref text, depart_utc text, on_time_probability real, route text, checked_utc text, primary key (user_id, ref))")
    return c


def _users() -> list[str]:
    with agent_store._conn() as c:
        rows = c.execute("select distinct user_id from commutes union select distinct user_id from goals").fetchall()
    return sorted({r[0] for r in rows})


def compare(previous: dict | None, current: dict) -> str | None:
    """The message a change deserves, or None."""
    if not previous or current.get("status") != "OK":
        return None
    old_t, new_t = datetime.fromisoformat(previous["depart_utc"]), datetime.fromisoformat(current["depart_utc"])
    moved = (new_t - old_t).total_seconds() / 60
    p_old, p_new = previous.get("on_time_probability") or 0.0, current.get("on_time_probability") or 0.0
    if moved <= -MOVE_MIN:
        return f"Leave earlier for {current['title']}: {current['depart_local']} instead of {old_t.astimezone(day.LOCAL).strftime('%H:%M')} ({round(-moved)} min earlier) — route {current['route']}, {round(p_new * 100)} % on time."
    if moved >= MOVE_MIN:
        return f"You can leave later for {current['title']}: {current['depart_local']} instead of {old_t.astimezone(day.LOCAL).strftime('%H:%M')} ({round(moved)} min later) — route {current['route']}."
    if p_old - p_new >= PROB_DROP:
        return f"Traffic on the way to {current['title']} is worse than planned: on-time chance fell from {round(p_old * 100)} % to {round(p_new * 100)} %; leave at {current['depart_local']} on route {current['route']}."
    if previous.get("route") and previous["route"] != current.get("route"):
        return f"Better route for {current['title']}: take route {current['route']} instead of {previous['route']} (leave {current['depart_local']})."
    return None


def tick(user_id: str | None = None) -> int:
    """Recompute every upcoming departure for one user (or all); publish a notification for every change. Returns the number of changes."""
    changes = 0
    for uid in ([user_id] if user_id else _users()):
        for d in day.departures(uid, hours=12.0):
            if d.get("status") != "OK":
                continue
            with _conn() as c:
                prev = c.execute("select * from watch where user_id=? and ref=?", (uid, d["ref"])).fetchone()
            msg = compare(dict(prev) if prev else None, d)
            if msg:
                notifications.publish(uid, "departure", msg, json.dumps({"ref": d["ref"], "depart_utc": d["depart_utc"], "route": d["route"], "on_time_probability": d["on_time_probability"]}))
                changes += 1
            with _LOCK, _conn() as c:
                c.execute("insert or replace into watch values (?,?,?,?,?,?)", (uid, d["ref"], d["depart_utc"], d["on_time_probability"], d["route"], now_iso()))
    return changes


def _loop() -> None:
    while True:
        try:
            _state["changes"] += tick(); _state["ticks"] += 1; _state["last_tick_utc"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:                        # noqa: BLE001 - recorded, never fatal
            _state["last_error"] = f"{type(exc).__name__}: {exc}"
        time.sleep(TICK_S)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="day-monitor", daemon=True)
    _thread.start()


def state() -> dict:
    return {**_state, "running": bool(_thread and _thread.is_alive()), "tick_s": TICK_S}
