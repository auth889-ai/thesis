"""Conflicts are found from the Life Twin's own facts: overlapping commitments, deadlines inside commitments or journeys, tight gaps (plan/conflicts.py)."""
from __future__ import annotations

from app.plan import conflicts

E = lambda t, s, e, loc="X": {"id": t, "title": t, "start_utc": f"2026-10-01T{s}:00+00:00", "end_utc": f"2026-10-01T{e}:00+00:00", "location": loc, "all_day": False}


def test_two_timed_commitments_that_overlap_are_a_high_conflict_with_the_overlap_named():
    c = conflicts.overlaps([E("Viva", "04:00", "05:00"), E("Class", "04:40", "06:00"), E("Lunch", "07:00", "08:00")])
    assert len(c) == 1 and c[0]["severity"] == "high" and c[0]["items"] == ["Viva", "Class"] and "overlap by 20 min" in c[0]["note"]


def test_an_all_day_item_never_overlaps():
    assert conflicts.overlaps([E("Viva", "04:00", "05:00"), {**E("Holiday", "00:00", "23:59"), "all_day": True}]) == []


def test_a_task_due_during_a_commitment_or_a_journey_is_a_deadline_conflict():
    tasks = [{"title": "submit report", "due_utc": "2026-10-01T04:30:00+00:00"}, {"title": "call bank", "due_utc": "2026-10-01T03:10:00+00:00"}, {"title": "no due", "due_utc": None}]
    deps = [{"status": "OK", "title": "Viva", "depart_utc": "2026-10-01T03:00:00+00:00", "depart_local": "09:00", "expected_s": 1500}]
    c = conflicts.deadlines(tasks, [E("Viva", "04:00", "05:00")], deps)
    assert [(x["items"][0], x["items"][1]) for x in c] == [("submit report", "Viva"), ("call bank", "Viva")]
    assert "on the way" in c[1]["note"] and "before you leave at 09:00" in c[1]["fix"]


def test_risky_and_impossible_gaps_become_conflicts_with_the_buffer_as_the_fix():
    checks = [{"from": "A", "to": "B", "grade": "feasible", "note": "fits", "buffer_min": 0}, {"from": "B", "to": "C", "grade": "impossible", "note": "does not fit", "buffer_min": 12}, {"from": "C", "to": "D", "grade": "risky", "note": "tight", "buffer_min": 5}]
    c = conflicts.gaps(checks)
    assert [(x["severity"], x["fix"]) for x in c] == [("high", "leave 'B' 12 min early, or move 'C'"), ("medium", "leave 'C' 5 min early, or move 'D'")]


def test_find_orders_by_severity_then_time():
    events = [E("Viva", "04:00", "05:00"), E("Class", "04:40", "06:00")]
    tasks = [{"title": "submit", "due_utc": "2026-10-01T04:30:00+00:00"}]
    c = conflicts.find(events, tasks, [], [{"from": "Viva", "to": "Class", "grade": "risky", "note": "tight", "buffer_min": 5}])
    assert [x["kind"] for x in c] == ["overlap", "gap", "deadline"] or [x["kind"] for x in c] == ["overlap", "deadline", "gap"]
    assert c[0]["severity"] == "high"
