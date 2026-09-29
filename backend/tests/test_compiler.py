"""P1: text becomes a validated Commitment; the rules path is deterministic, the model path is validated, and both are served (lifeos/compiler)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agent.llm import Scripted, Turn
from app.lifeos import db, repo
from app.lifeos.compiler import model as model_path, rules, service
from app.lifeos.entities import Person, Place

NOW = datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)                  # Wednesday 09:00 Dhaka
TZ = "Asia/Dhaka"
KNOWN = [Place(name="Mirpur", kind="home"), Place(name="Evercare Hospital", kind="saved"), Place(name="IUT", kind="work")]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'lifeos.sqlite'}"; monkeypatch.setenv("LIFEOS_DATABASE_URL", url); db.init(url)


def local(c):
    return (c.start or c.deadline).astimezone(__import__("zoneinfo").ZoneInfo(TZ)).strftime("%a %Y-%m-%d %H:%M")


def test_the_rules_read_type_time_place_and_requirements():
    r = rules.compile_rules("Interview at TechNova in Banani on Friday 10 AM, bring CV and ID", "eva", NOW, TZ, KNOWN); c = r["commitment"]
    assert c.type.value == "interview" and local(c) == "Fri 2026-10-02 10:00" and c.location.name == "TechNova, Banani" and c.requirements == ["CV", "ID"] and c.flexibility.value == "fixed" and r["missing"] == []


def test_a_deadline_is_anytime_before_and_a_saved_place_is_snapped():
    c = rules.compile_rules("Submit the thesis report by 6 PM", "eva", NOW, TZ, KNOWN)["commitment"]
    assert c.type.value == "deadline" and c.flexibility.value == "anytime_before" and c.start is None and local(c) == "Wed 2026-09-30 18:00"
    c = rules.compile_rules("Doctor at Evercare next Friday 3 pm", "eva", NOW, TZ, KNOWN)["commitment"]
    assert c.location.name == "Evercare Hospital" and c.location.kind == "saved" and local(c) == "Fri 2026-10-09 15:00"


def test_relative_days_and_durations():
    assert local(rules.compile_rules("Class at IUT tomorrow 9am for 2 hours", "eva", NOW, TZ, KNOWN)["commitment"]) == "Thu 2026-10-01 09:00"
    assert rules.compile_rules("Class at IUT tomorrow 9am for 2 hours", "eva", NOW, TZ, KNOWN)["commitment"].duration_min == 120
    assert local(rules.compile_rules("Interview Wednesday 10am", "eva", NOW, TZ, KNOWN)["commitment"]) == "Wed 2026-10-07 10:00"     # a Wednesday said on a Wednesday is next week's
    assert local(rules.compile_rules("Report due by 2026-10-03 17:00", "eva", NOW, TZ, KNOWN)["commitment"]) == "Sat 2026-10-03 17:00"
    assert local(rules.compile_rules("Meeting at 8am", "eva", NOW, TZ, KNOWN)["commitment"]) == "Thu 2026-10-01 08:00"             # 8 am has passed at 09:00: tomorrow


def test_a_day_without_a_time_is_not_an_instant():
    r = rules.compile_rules("Dinner with Rafi tomorrow", "eva", NOW, TZ, KNOWN)
    assert r["commitment"] is None and "time" in r["missing"]


def test_the_model_path_is_validated_and_falls_back_to_the_rules():
    good = Scripted([Turn(text="", tool_calls=[{"name": "commitment__record", "input": {"title": "Interview at TechNova", "type": "interview", "location": "TechNova, Banani", "start_local": "2026-10-02T10:00", "deadline_local": "2026-10-02T10:00", "flexibility": "fixed", "requirements": ["CV", "ID"], "missing": []}, "id": "t1"}])])
    r = model_path.compile_model("Friday 10 AM interview at TechNova in Banani, bring CV and ID", "eva", NOW, TZ, KNOWN, good)
    assert r["commitment"].type.value == "interview" and local(r["commitment"]) == "Fri 2026-10-02 10:00" and r["confidence"] == 1.0
    bad = Scripted([Turn(text="", tool_calls=[{"name": "commitment__record", "input": {"title": "x", "type": "interview", "start_local": "2026-10-02T10:00", "deadline_local": "2026-10-02T09:00", "flexibility": "fixed"}, "id": "t2"}])])
    with pytest.raises(Exception):
        model_path.compile_model("x", "eva", NOW, TZ, KNOWN, bad)                          # deadline before start: refused by the contract
    bad_again = Scripted([Turn(text="", tool_calls=[{"name": "commitment__record", "input": {"title": "x", "type": "interview", "start_local": "2026-10-02T10:00", "deadline_local": "2026-10-02T09:00", "flexibility": "fixed"}, "id": "t3"}])])
    r = service.compile("Interview at Banani on Friday 10 AM", "eva", llm=bad_again, now=NOW)
    assert r["path"] == "rules" and r["model_error"].startswith("ValidationError") and r["commitment"]["type"] == "interview"


def test_compile_uses_the_persons_zone_and_places_and_can_save():
    with db.session() as s:
        repo.put_person(s, Person(id="ava", timezone="America/Los_Angeles", home=Place(name="Silver Lake"), places=[Place(name="UCLA", kind="saved")]))
    r = service.compile("Exam at ucla tomorrow 9 am, bring ID", "ava", now=NOW, save=True)
    assert r["timezone"] == "America/Los_Angeles" and r["commitment"]["location"]["name"] == "UCLA" and r["saved"] is True
    assert r["commitment"]["deadline"].startswith("2026-09-30T16:00:00")                  # 09:00 Los Angeles on the 30th, in UTC
    with db.session() as s:
        assert [c.title for c in repo.list_for(s, "commitment", "ava")] == ["Exam at UCLA"]


def test_compile_over_http(client):
    r = client.post("/api/lifeos/compile", json={"person_id": "p1", "text": "Viva on 2 October at 11:00 at Shahbagh", "use_model": False}).json()
    assert r["path"] == "rules" and r["commitment"]["type"] == "exam" and r["commitment"]["location"]["name"] == "Shahbagh" and r["saved"] is not True
