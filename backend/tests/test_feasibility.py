"""Gaps between commitments are graded from the departure distribution, never from a fixed rule (plan/feasibility.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.plan import feasibility, outcomes

T0 = datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc)                  # 11:00 Dhaka: the first commitment ends
EV = [{"id": "a", "title": "Meeting", "start_utc": (T0 - timedelta(hours=1)).isoformat(), "end_utc": T0.isoformat(), "location": "Farmgate", "all_day": False},
      {"id": "b", "title": "Class", "start_utc": (T0 + timedelta(minutes=30)).isoformat(), "end_utc": (T0 + timedelta(minutes=90)).isoformat(), "location": "IUT", "all_day": False}]


def planner(p_at_end: float, expected_min: int, rec_before_end_min: int):
    """A commute plan whose slot nearest the end time has the given probability, and whose recommended departure is earlier."""
    def plan(city, origin, destination, arrive_by, now):
        slots = [{"depart_utc": (T0 + timedelta(minutes=m)).isoformat(), "depart_local": f"{11 + m // 60:02d}:{m % 60:02d}", "expected_s": expected_min * 60, "on_time_probability": max(0.0, p_at_end - 0.1 * (m // 5)), "best_route": "A"} for m in range(-60, 31, 5)]
        rec = {"depart_utc": (T0 - timedelta(minutes=rec_before_end_min)).isoformat(), "depart_local": f"{(T0 - timedelta(minutes=rec_before_end_min)).hour + 6:02d}:{(T0 - timedelta(minutes=rec_before_end_min)).minute:02d}", "on_time_probability": 0.8, "route": "A"}
        return {"departures": slots, "recommended": rec, "provenance": {}}
    return plan


@pytest.fixture(autouse=True)
def no_calibration(tmp_path, monkeypatch):
    monkeypatch.setattr(outcomes, "DB", tmp_path / "o.sqlite")


def test_grades_come_from_the_probability_of_leaving_as_the_first_ends():
    assert feasibility.grade(0.95) == "feasible" and feasibility.grade(0.8) == "feasible"
    assert feasibility.grade(0.79) == "risky" and feasibility.grade(0.5) == "risky"
    assert feasibility.grade(0.49) == "impossible" and feasibility.grade(None) == "unknown"


def test_a_tight_gap_is_risky_and_says_how_much_earlier_to_leave():
    c = feasibility.assess("u", EV, plan=planner(0.65, 25, 10), now=T0 - timedelta(hours=3))[0]
    assert c["grade"] == "risky" and c["feasible"] is False and c["gap_min"] == 30 and c["needed_min"] == 25 and c["buffer_min"] == 10
    assert "leave 10 min before the end" in c["note"]
    assert feasibility.verdict([c]) == "this schedule can work, but one gap is tight"


def test_a_gap_that_cannot_hold_the_journey_is_impossible():
    c = feasibility.assess("u", EV, plan=planner(0.3, 47, 25), now=T0 - timedelta(hours=3))[0]
    assert c["grade"] == "impossible" and c["buffer_min"] == 25 and "47 min" in c["note"]
    assert feasibility.verdict([c]) == "this schedule does not fit as it stands"


def test_a_comfortable_gap_is_feasible_with_no_buffer():
    c = feasibility.assess("u", EV, plan=planner(0.9, 12, 0), now=T0 - timedelta(hours=3))[0]
    assert c["grade"] == "feasible" and c["feasible"] is True and c["buffer_min"] == 0
    assert feasibility.verdict([c]) == "this schedule can work"


def test_the_persons_calibration_scales_the_journey_time():
    for _ in range(3):
        outcomes.record("slow", "r", "A", "B", 600, None, "2026-09-29T02:00:00+00:00", "2026-09-29T02:15:00+00:00", "2026-09-29T03:00:00+00:00")   # 1.5× slower than predicted
    c = feasibility.assess("slow", EV, plan=planner(0.9, 20, 0), now=T0 - timedelta(hours=3))[0]
    assert c["needed_min"] == 30


def test_an_unplannable_gap_is_unknown_not_hidden():
    def broken(*a): raise ValueError("'Nowhere' was not found inside Dhaka")
    c = feasibility.assess("u", EV, plan=broken)[0]
    assert c["grade"] == "unknown" and c["feasible"] is None and "Nowhere" in c["note"]
    assert feasibility.verdict([c]) == "no gap could be checked"


def test_only_placed_timed_commitments_are_checked_in_order():
    ev = [EV[1], EV[0], {"id": "c", "title": "Holiday", "start_utc": T0.isoformat(), "end_utc": T0.isoformat(), "location": "", "all_day": True}]
    c = feasibility.assess("u", ev, plan=planner(0.9, 12, 0), now=T0 - timedelta(hours=3))
    assert [(x["from"], x["to"]) for x in c] == [("Meeting", "Class")]
