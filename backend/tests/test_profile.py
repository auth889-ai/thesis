"""A person has a name, a zone, a city, a home and a target; every module reads them instead of a fixed place (app/profile)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import config
from app.plan import conflicts, day, feasibility
from app.profile import service, store


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "profiles.sqlite")
    from app.plan import outcomes
    monkeypatch.setattr(outcomes, "DB", tmp_path / "o.sqlite")


def test_without_a_profile_the_deployment_defaults_apply_and_say_so():
    c = service.context("nobody")
    assert c["exists"] is False and c["city"] == config.DEFAULT_CITY and c["timezone"] == config.DEFAULT_TZ and c["source"] == "deployment default"


def test_the_persons_zone_city_home_and_target_are_read_everywhere():
    store.save("la", name="Ava", timezone="America/Los_Angeles", city="Los Angeles", home="Silver Lake", on_time_target=0.9)
    assert service.city_for("la") == "Los Angeles" and service.home_for("la") == "Silver Lake" and service.target_for("la") == 0.9
    assert str(service.tz_for("la")) == "America/Los_Angeles"
    at = datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)
    assert service.local_clock("la", at).strftime("%H:%M") == "09:00"
    assert day._home("la") == "Silver Lake"
    assert conflicts.find([], [{"title": "x", "due_utc": at.isoformat()}], [], [], service.tz_for("la")) == []
    assert feasibility.grade(0.85, service.target_for("la")) == "risky" and feasibility.grade(0.85) == "feasible"


def test_the_planner_receives_the_persons_zone_and_target(monkeypatch):
    store.save("la", timezone="America/Los_Angeles", city="Los Angeles", on_time_target=0.9)
    seen = {}
    def fake_plan(city, o, d, arrive_by, **kw):
        seen.update(city=city, tz=str(kw.get("tz")), target=kw.get("target"))
        return {"recommended": {"depart_utc": arrive_by.isoformat(), "depart_local": "x", "route": "A", "on_time_probability": 0.9, "expected_s": 600}, "departures": [], "provenance": {}}
    from app.commute import service as commute
    monkeypatch.setattr(commute, "plan", fake_plan)
    r = day.departure_for("la", "Silver Lake", "Downtown", datetime(2026, 10, 1, 17, 0, tzinfo=timezone.utc), "r", "t")
    assert seen == {"city": "Los Angeles", "tz": "America/Los_Angeles", "target": 0.9} and r["arrive_by_local"] == "10:00"


def test_a_floating_calendar_time_is_read_in_the_persons_zone():
    from app.calendar import ics
    utc_iso, all_day = ics.parse_dt("20261001T090000", "", service.zone("America/Los_Angeles"))
    assert utc_iso.startswith("2026-10-01T16:00:00") and not all_day


def test_locate_names_the_city_at_a_point(monkeypatch):
    from core.simulation.routing.trip import places
    monkeypatch.setattr(places, "reverse_geocode", lambda lat, lng: {"display_name": "Farmgate, Dhaka, Bangladesh", "address": {"city": "Dhaka", "country": "Bangladesh"}})
    assert service.locate(23.75, 90.39)["city"] == "Dhaka"


def test_profile_over_http_round_trips_and_rejects_a_bad_zone(client):
    assert client.put("/api/profile", json={"user_id": "p1", "timezone": "Mars/Olympus"}).status_code == 422
    r = client.put("/api/profile", json={"user_id": "p1", "name": "Jana", "timezone": "Asia/Dhaka", "city": "Dhaka", "home": "Mirpur", "on_time_target": 0.9}).json()
    assert r["exists"] and r["name"] == "Jana" and r["home"] == "Mirpur" and r["on_time_target"] == 0.9 and r["source"] == "person"
    assert client.get("/api/profile?user_id=p1").json()["city"] == "Dhaka"
