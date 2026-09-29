"""What actually happened, and what it teaches: a person records when they left and arrived; the ratio of
actual to predicted travel time, over their last trips, calibrates their future plans."""
from __future__ import annotations

import sqlite3
import statistics
from datetime import datetime

from app.agent.models import RiskClass, new_id, now_iso
from app.agent.store import DB, _LOCK

MIN_TRIPS = 3
CLAMP = (0.6, 2.5)


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False); c.row_factory = sqlite3.Row
    c.execute("create table if not exists outcomes (id text primary key, user_id text, ref text, origin text, destination text, predicted_s real, recommended_depart_utc text, departed_utc text, arrived_utc text, deadline_utc text, on_time integer, created_utc text)")
    return c


def record(user_id: str, ref: str, origin: str, destination: str, predicted_s: float | None, recommended_depart_utc: str | None, departed_utc: str, arrived_utc: str, deadline_utc: str | None) -> dict:
    on_time = None
    if deadline_utc:
        on_time = 1 if datetime.fromisoformat(arrived_utc) <= datetime.fromisoformat(deadline_utc) else 0
    row = {"id": new_id("out"), "user_id": user_id, "ref": ref, "origin": origin, "destination": destination, "predicted_s": predicted_s, "recommended_depart_utc": recommended_depart_utc,
           "departed_utc": departed_utc, "arrived_utc": arrived_utc, "deadline_utc": deadline_utc, "on_time": on_time, "created_utc": now_iso()}
    with _LOCK, _conn() as c:
        c.execute("insert into outcomes values (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
    return row


def list_for(user_id: str, limit: int = 30) -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from outcomes where user_id=? order by created_utc desc limit ?", (user_id, limit)).fetchall()]


def calibration(user_id: str) -> dict:
    """Median actual / predicted travel time over the person's recorded trips; 1.0 until there are enough."""
    rows = [r for r in list_for(user_id, 50) if r["predicted_s"] and r["departed_utc"] and r["arrived_utc"]]
    ratios = []
    for r in rows:
        actual = (datetime.fromisoformat(r["arrived_utc"]) - datetime.fromisoformat(r["departed_utc"])).total_seconds()
        if actual > 0 and r["predicted_s"] > 0:
            ratios.append(actual / r["predicted_s"])
    if len(ratios) < MIN_TRIPS:
        return {"factor": 1.0, "trips": len(ratios), "basis": f"needs {MIN_TRIPS} recorded trips; using the city's distribution as is"}
    f = max(CLAMP[0], min(CLAMP[1], statistics.median(ratios)))
    on_time = [r["on_time"] for r in rows if r["on_time"] is not None]
    return {"factor": round(f, 3), "trips": len(ratios), "on_time_rate": round(sum(on_time) / len(on_time), 2) if on_time else None,
            "basis": f"median of actual over predicted travel time on your last {len(ratios)} trips"}


def tool_record(user_id, a, goal_id):
    return record(user_id, a.get("ref", "trip"), a.get("origin", ""), a.get("destination", ""), a.get("predicted_s"), a.get("recommended_depart"), a["departed"], a["arrived"], a.get("deadline"))


TOOL_SPECS = [
    ("outcomes.record", "Record how a trip actually went (ISO times): when the person left and arrived, and the deadline if any. Improves their future on-time estimates.",
     {"type": "object", "properties": {"ref": {"type": "string"}, "origin": {"type": "string"}, "destination": {"type": "string"}, "predicted_s": {"type": "number"}, "recommended_depart": {"type": "string"}, "departed": {"type": "string"}, "arrived": {"type": "string"}, "deadline": {"type": "string"}}, "required": ["departed", "arrived"]}, RiskClass.WRITE_REVERSIBLE, tool_record),
]
