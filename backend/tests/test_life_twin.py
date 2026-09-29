"""Intent records, the Life Twin snapshot with its feasibility check, and the what-if verdicts."""
from datetime import datetime, timedelta, timezone

import pytest

from app.agent import intent
from app.plan import life_twin, whatif


@pytest.fixture
def user(tmp_path, monkeypatch):
    from app.agent import store
    for mod in ("app.agent.store", "app.agent.memory", "app.calendar.store", "app.plan.notifications", "app.plan.outcomes", "app.plan.monitor"):
        monkeypatch.setattr(__import__(mod, fromlist=["DB"]), "DB", tmp_path / "agent.sqlite")
    return "u-twin"


def test_rule_based_intent_reads_type_deadline_domains_and_missing_facts():
    d = intent.by_rules("I have an interview tomorrow at 10 AM. Make sure I am prepared and reach there on time.", now=datetime(2026, 9, 29, 12, 0))
    assert d["goal_type"] == "interview" and d["deadline_local"] == "2026-09-30T10:00" and {"calendar", "mobility", "tasks"} <= set(d["domains"]) and d["source"] == "rules"
    assert "a destination" in d["missing"] and d["needs_approval"] is False
    assert intent.by_rules("Send the recruiter a reply and book the room")["needs_approval"] is True


def test_intent_extract_uses_the_forced_tool_and_falls_back_to_rules():
    from app.agent.llm import Scripted, Turn
    llm = Scripted([Turn(text="", tool_calls=[{"name": "intent__record", "input": {"goal_type": "exam", "objectives": ["pass"], "domains": ["tasks", "nowhere"]}, "id": "i1"}])])
    d = intent.extract("exam in a week", llm)
    assert d["goal_type"] == "exam" and d["domains"] == ["tasks"] and d["source"] == "scripted" and llm.calls[0]["tools"] == ["intent__record"]
    assert intent.extract("plan my day tomorrow", Scripted([]))["goal_type"] == "planning"


def test_life_twin_flags_an_infeasible_gap_and_finds_free_windows(user, monkeypatch):
    from app.calendar import store as cal
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    t1 = now + timedelta(hours=2); t2 = t1 + timedelta(hours=1)
    cal.upsert(user, {"uid": "a", "title": "Interview", "start_utc": t1.isoformat(), "end_utc": t2.isoformat(), "location": "Banani"}, "t")
    cal.upsert(user, {"uid": "b", "title": "Class", "start_utc": (t2 + timedelta(minutes=30)).isoformat(), "end_utc": (t2 + timedelta(minutes=90)).isoformat(), "location": "Shahbagh"}, "t")
    from app.commute import service
    monkeypatch.setattr(service, "plan", lambda city, o, d, arrive_by, **kw: {"recommended": {"depart_utc": (arrive_by - timedelta(minutes=50)).isoformat(), "route": "A", "on_time_probability": 0.85, "expected_s": 2820}, "provenance": {}})
    s = life_twin.snapshot(user, 24)
    leg = next(c for c in s["feasibility"] if c["from"] == "Interview")
    assert leg["feasible"] is False and leg["gap_min"] == 30 and leg["needed_min"] == 47 and "does not fit" in s["verdict"]
    assert s["free_windows"] and s["free_windows"][0]["minutes"] >= 30 and len(s["departures"]) == 2


def test_what_if_verdicts_prefer_on_time_then_rail_then_an_earlier_departure():
    assert "still arrives on time" in whatif._verdict(0.9, 0, False, "07:50")
    assert "rail option" in whatif._verdict(0.4, 5, True, "07:50")
    assert "leave by 07:50" in whatif._verdict(0.4, 12, False, "07:50")
    assert "gamble" in whatif._verdict(0.5, 0, False, "07:50")
