"""The commute planner: a plan that respects the deadline, probabilities only from the city's own observed history,
honest labels when there is none, and a route that can be watched."""
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DHAKAFLOW_NO_OBSERVATORY", "1")
DHAKA = timezone(timedelta(hours=6))


def _rows(n_days=3, speeds=(10.0, 4.0)):
    """Own readings for two corridors every 15 min for n_days: corridor A free, corridor B slow in the mornings."""
    rows, nodes = [], ["farmgate_to_shahbagh", "shahbagh_to_farmgate"]
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for i in range(n_days * 96):
        t = t0 + timedelta(minutes=15 * i)
        local_h = (t + timedelta(hours=6)).hour
        b = speeds[1] if 7 <= local_h < 10 else speeds[0]
        rows.append({"t": t.timestamp(), "utc": t.isoformat(), "provider": "probes", "v": [speeds[0], b]})
    return rows, nodes


def test_profiles_come_from_own_readings_only(monkeypatch):
    from app.commute import history
    from core.common.data.live_providers import observatory as obs
    rows, nodes = _rows()
    rows.append({"t": 0, "utc": "2026-09-05T08:00:00+00:00", "provider": "google", "v": [1.0, 1.0]})     # must be ignored
    monkeypatch.setattr(obs.observatory, "series", lambda city: (rows, nodes))
    history.forget()
    prof = history.own_profiles("dhaka", 6)
    assert set(prof["corridors"]) == set(nodes) and prof["samples"] == 2 * len(rows) - 2
    morning = history.multiplier_distribution(prof, "shahbagh_to_farmgate", (8 * 60) // 15)
    night = history.multiplier_distribution(prof, "shahbagh_to_farmgate", (2 * 60) // 15)
    assert min(morning) > 2.0 and max(night) == 1.0                                       # 10 / 4 = 2.5 in the morning, free at night


def test_plan_uses_own_history_and_says_when_there_is_none(monkeypatch):
    from app.commute import history, service
    from core.common.data.live_providers import observatory as obs
    rows, nodes = _rows()
    monkeypatch.setattr(obs.observatory, "series", lambda city: (rows, nodes))
    monkeypatch.setattr(obs.observatory, "cities", lambda: ["dhaka"])
    monkeypatch.setattr(obs.observatory, "own_history", lambda city: {"steps_own": len(rows)})
    history.forget()
    routes = [{"static_duration_s": 600.0, "distance_m": 5000, "corridors_touched": ["shahbagh_to_farmgate"], "description": "A"}]
    monkeypatch.setattr(service, "_routes", lambda city, o, d: ({"lat": 23.75, "lng": 90.39}, {"lat": 23.73, "lng": 90.40}, routes, {"_routing_words": "test roads"}))
    now = datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc)                                 # 08:00 Dhaka, inside the slow morning (slots pool ±15 min)
    r = service.plan("dhaka", "Farmgate", "Shahbagh", now + timedelta(hours=1), now=now, tz=DHAKA)
    assert r["provenance"]["kind"] == "OWN_OBSERVED" and r["coverage"]["covered"] and r["recommended"]["on_time_probability"] is not None
    assert r["departures"][0]["options"][0]["expected_s"] == 1500                         # 600 s × 2.5 in the morning
    assert r["recommended"]["expected_s"] >= 600
    # the same route in a city with no readings: no probability, a reason, an action
    monkeypatch.setattr(obs.observatory, "series", lambda city: ([], nodes))
    monkeypatch.setattr(obs.observatory, "cities", lambda: [])
    history.forget()
    r2 = service.plan("gazipur", "Farmgate", "Shahbagh", now + timedelta(hours=1), now=now, tz=DHAKA)
    assert r2["provenance"]["kind"] == "ROUTING_ONLY" and r2["recommended"]["on_time_probability"] is None
    assert r2["coverage"]["watched"] is False and "no observed traffic for this city yet" in r2["coverage"]["action"]
    assert "free-flow route time" in r2["provenance"]["traffic"] and r2["routes"][0]["static_s"] == 600.0     # the free-flow time stays, labelled


def test_plan_refuses_a_past_deadline():
    from app.commute import service
    with pytest.raises(ValueError):
        service.plan("dhaka", "Farmgate", "Shahbagh", datetime.now(timezone.utc) - timedelta(hours=1))


def test_watch_route_adds_a_corridor_and_starts_the_recorder(monkeypatch, tmp_path):
    from app.commute import service
    from core.common.data import city_corridors
    from core.common.data.live_providers import observatory as obs
    monkeypatch.setattr(city_corridors, "corridors_file", lambda cid: tmp_path / f"{cid}.json")
    monkeypatch.setattr(city_corridors, "derive", lambda cid, k: [])
    monkeypatch.setattr("core.simulation.routing.trip_analysis.resolve_place", lambda place, city: {"lat": 23.9, "lng": 90.4, "label": place})
    started = []
    monkeypatch.setattr(obs.observatory, "start", lambda cid: started.append(cid) or {"running": True})
    r = service.watch_route("Gazipur", "Tongi", "Joydebpur")
    assert r["city_id"] == "gazipur" and started == ["gazipur"] and len(r["corridors_added"]) == 1
    assert city_corridors.load("gazipur")[0]["road"] == "user route"


def test_endpoint_shape(client):
    r = client.post("/api/commute/plan", json={"city": "dhaka", "origin": "Farmgate", "destination": "Shahbagh", "arrive_by": (datetime.now(DHAKA) + timedelta(hours=2)).isoformat()})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        j = r.json(); assert {"recommended", "routes", "departures", "day_profile", "coverage", "provenance"} <= set(j)
        assert j["provenance"]["kind"] in ("OWN_OBSERVED", "ROUTING_ONLY") and "Google" not in j["provenance"]["traffic"]
