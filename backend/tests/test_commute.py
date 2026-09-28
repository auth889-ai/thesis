"""The commute planner: recorded time-of-day profile, a plan that respects the deadline, honest labels."""
from datetime import datetime, timedelta, timezone

import pytest

from app.commute import service


def test_profile_has_every_slot_and_recorded_samples():
    p = service.profile("farmgate_to_shahbagh")
    assert len(p["slots"]) == 96 and p["provenance"]["kind"] == "TYPICAL_RECORDED"
    assert sum(s["samples"] for s in p["slots"]) > 1000
    assert all(0 <= (s["expected_level"] or 0) <= 3 for s in p["slots"])


def test_plan_recommends_a_departure_before_the_deadline_with_a_probability():
    now = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)             # 07:00 Dhaka
    arrive = now + timedelta(hours=2)
    r = service.plan("dhaka", "Farmgate", "Shahbagh", arrive, now=now)
    rec = r["recommended"]
    assert datetime.fromisoformat(rec["depart_utc"]) < arrive and rec["route"] in ("A", "B", "C")
    assert rec["on_time_probability"] is not None and 0 <= rec["on_time_probability"] <= 1        # the Farmgate→Shahbagh routes run along recorded corridors
    assert any(rt["corridors"] for rt in r["routes"]) and r["congestion_window"] is not None
    assert len(r["routes"]) >= 1 and len(r["day_profile"]) == 96 and r["departures"]
    assert r["provenance"]["kind"] == "TYPICAL_RECORDED" and "not live" in r["provenance"]["traffic"]
    # a later deadline never lowers the on-time probability of the same departure
    later = service.plan("dhaka", "Farmgate", "Shahbagh", arrive + timedelta(hours=1), now=now)
    assert (later["departures"][0]["on_time_probability"] or 0) >= (r["departures"][0]["on_time_probability"] or 0)


def test_plan_refuses_a_past_deadline():
    with pytest.raises(ValueError):
        service.plan("dhaka", "Farmgate", "Shahbagh", datetime.now(timezone.utc) - timedelta(minutes=1))


def test_endpoint_shape(client):
    r = client.post("/api/commute/plan", json={"city": "dhaka", "origin": "Farmgate", "destination": "Shahbagh", "arrive_by": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})
    assert r.status_code == 200, r.text
    d = r.json(); assert {"recommended", "routes", "departures", "day_profile", "congestion_window", "provenance"} <= set(d)
    assert client.get("/api/commute/profile?corridor=farmgate_to_shahbagh").status_code == 200
    assert client.get("/api/commute/profile?corridor=nope").status_code == 404
