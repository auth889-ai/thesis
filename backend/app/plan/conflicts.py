"""CONFLICTS — things in the person's day that collide, found from the Life Twin's own facts:
    overlap        two timed commitments overlap
    deadline       a task is due while the person is in a commitment, or on the road for one
    gap            a gap between two placed commitments is risky or impossible (plan/feasibility.py)
Each conflict names the items, the local time, the severity and one concrete fix. Pure functions over the
snapshot's lists so they are tested without a calendar or a planner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

LOCAL = timezone(timedelta(hours=6))                   # default only; find() takes the person's zone


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _local(iso: str, tz=LOCAL) -> str:
    return _dt(iso).astimezone(tz).strftime("%a %H:%M")


def overlaps(events: list[dict], tz=LOCAL) -> list[dict]:
    timed = sorted((e for e in events if not e.get("all_day")), key=lambda e: e["start_utc"])
    out = []
    for i, a in enumerate(timed):
        for b in timed[i + 1:]:
            if _dt(b["start_utc"]) < _dt(a["end_utc"]):
                mins = round((min(_dt(a["end_utc"]), _dt(b["end_utc"])) - _dt(b["start_utc"])).total_seconds() / 60)
                out.append({"kind": "overlap", "severity": "high", "items": [a["title"], b["title"]], "when_local": _local(b["start_utc"], tz),
                            "note": f"'{a['title']}' and '{b['title']}' overlap by {mins} min", "fix": "move or shorten one of them"})
    return out


def deadlines(tasks: list[dict], events: list[dict], departures: list[dict], tz=LOCAL) -> list[dict]:
    out = []
    for t in tasks:
        if not t.get("due_utc"):
            continue
        due = _dt(t["due_utc"])
        for e in events:
            if not e.get("all_day") and _dt(e["start_utc"]) <= due < _dt(e["end_utc"]):
                out.append({"kind": "deadline", "severity": "medium", "items": [t["title"], e["title"]], "when_local": _local(t["due_utc"], tz),
                            "note": f"'{t['title']}' is due during '{e['title']}'", "fix": f"finish it before {_local(e['start_utc'], tz).split(' ')[1]} or move the deadline"})
        for d in departures:
            if d.get("status") == "OK" and _dt(d["depart_utc"]) <= due < _dt(d["depart_utc"]) + timedelta(seconds=d["expected_s"]):
                out.append({"kind": "deadline", "severity": "medium", "items": [t["title"], d["title"]], "when_local": _local(t["due_utc"], tz),
                            "note": f"'{t['title']}' is due while you are on the way to '{d['title']}'", "fix": f"finish it before you leave at {d['depart_local']}"})
    return out


def gaps(checks: list[dict]) -> list[dict]:
    out = []
    for c in checks:
        if c.get("grade") in ("risky", "impossible"):
            out.append({"kind": "gap", "severity": "high" if c["grade"] == "impossible" else "medium", "items": [c["from"], c["to"]], "when_local": None,
                        "note": c["note"], "fix": (f"leave '{c['from']}' {c['buffer_min']} min early, or move '{c['to']}'" if c.get("buffer_min") else "leave the moment it ends")})
    return out


def find(events: list[dict], tasks: list[dict], departures: list[dict], checks: list[dict], tz=LOCAL) -> list[dict]:
    """Every conflict, highest severity first, then by time, with times in the person's zone."""
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(overlaps(events, tz) + deadlines(tasks, events, departures, tz) + gaps(checks), key=lambda c: (order[c["severity"]], c["when_local"] or ""))
