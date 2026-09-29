"""Phase 0: the seven contracts validate, survive a round trip through the migrated store, and are served over HTTP."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.lifeos import db, repo
from app.lifeos.entities import Action, Commitment, Constraint, Event, EventKind, Flexibility, Outcome, Person, Place, TravelEdge, Uncertainty

T = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)                    # 09:00 Dhaka


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'lifeos.sqlite'}"
    monkeypatch.setenv("LIFEOS_DATABASE_URL", url)
    assert db.init(url) == "0001_lifeos_core"


def test_a_commitment_must_be_coherent():
    ok = Commitment(id="c1", person_id="eva", title="Interview", type="interview", location=Place(name="Banani"), start=T + timedelta(hours=7), deadline=T + timedelta(hours=7), requirements=["CV", "ID"])
    assert ok.priority.value == "should" and ok.start.tzinfo is not None
    with pytest.raises(ValidationError, match="timezone"):
        Commitment(id="c2", person_id="eva", title="x", start=datetime(2026, 10, 2, 9), deadline=T)
    with pytest.raises(ValidationError, match="before start"):
        Commitment(id="c3", person_id="eva", title="x", start=T, deadline=T - timedelta(minutes=1))
    with pytest.raises(ValidationError, match="needs a start"):
        Commitment(id="c4", person_id="eva", title="x", deadline=T)
    with pytest.raises(ValidationError, match="window_start"):
        Commitment(id="c5", person_id="eva", title="x", deadline=T, flexibility=Flexibility.MOVABLE)
    with pytest.raises(ValidationError, match="depend on itself"):
        Commitment(id="c6", person_id="eva", title="x", start=T, deadline=T, depends_on=["c6"])


def test_a_travel_edge_carries_its_provenance_and_ordered_uncertainty():
    e = TravelEdge(id="e1", person_id="eva", origin=Place(name="Home"), destination=Place(name="Banani"), mode="car", depart=T, duration_s=2520, uncertainty=Uncertainty(p10_s=2100, p50_s=2520, p90_s=3360, method="conformal"), provider="valhalla", freshness="typical")
    assert e.arrive == T + timedelta(seconds=2520) and e.freshness.value == "typical"
    with pytest.raises(ValidationError, match="p10 <= p50 <= p90"):
        Uncertainty(p10_s=3000, p50_s=2000)
    with pytest.raises(ValidationError):
        TravelEdge(id="e2", person_id="eva", origin=Place(name="a"), destination=Place(name="b"), mode="teleport", depart=T, duration_s=1, provider="x")


def test_every_entity_round_trips_through_the_store():
    with db.session() as s:
        repo.put(s, Person(id="eva", name="Eva", timezone="Asia/Dhaka", city="Dhaka", home=Place(name="Mirpur", lat=23.8, lng=90.37)))
        c = repo.put(s, Commitment(id="c1", person_id="eva", title="Class", type="class", location=Place(name="IUT"), start=T, deadline=T, duration_min=90, priority="must"))
        repo.put(s, Commitment(id="c2", person_id="eva", title="Interview", type="interview", location=Place(name="Banani"), start=T + timedelta(hours=7), deadline=T + timedelta(hours=7), depends_on=["c1"]))
        repo.put(s, Constraint(id="k1", person_id="eva", kind="weather", params={"rain_mm": 12}, severity="soft"))
        repo.put(s, TravelEdge(id="e1", person_id="eva", origin=Place(name="Mirpur"), destination=Place(name="IUT"), mode="transit", depart=T - timedelta(hours=1), duration_s=3000, provider="static"))
        repo.put(s, Outcome(id="o1", person_id="eva", commitment_id="c1", on_time=True, forecast_error_s=-120))
        repo.put(s, Action(id="a1", person_id="eva", tool="calendar.create_event", risk="write_reversible", decision="allow", goal_id="g1"))
        repo.put(s, Event(id="v1", person_id="eva", kind=EventKind.CALENDAR_CHANGED, payload={"commitment_id": "c2"}, occurred_at=T))
        assert repo.get(s, "commitment", "c1") == c
        day = repo.commitments_between(s, "eva", T - timedelta(hours=1), T + timedelta(hours=12))
        assert [x.id for x in day] == ["c1", "c2"] and day[1].depends_on == ["c1"]
        assert [e.kind for e in repo.events_since(s, T - timedelta(days=1), "eva")] == [EventKind.CALENDAR_CHANGED]
        eva = repo.get(s, "person", "eva"); assert eva.home.lat == 23.8 and eva.home.kind == "home"
        from sqlalchemy import text
        assert [r[0] for r in s.execute(text("select name from sqlite_master where type='table' order by name"))] == ["actions", "alembic_version", "commitment_dependencies", "commitment_requirements", "commitments", "constraint_params", "constraint_targets", "constraints", "events", "outcomes", "persons", "places", "travel_edges"]
        assert s.execute(text("select item from commitment_requirements where commitment_id='c1'")).fetchall() == []
        assert s.execute(text("select depends_on_id from commitment_dependencies where commitment_id='c2'")).fetchall() == [("c1",)]
        assert s.execute(text("select key, value from constraint_params where constraint_id='k1'")).fetchall() == [("rain_mm", "12")]
        assert s.execute(text("select count(*) from places where person_id='eva'")).scalar() == 3          # Mirpur (home), IUT, Banani
        assert repo.delete(s, "outcome", "o1") and repo.get(s, "outcome", "o1") is None


def test_the_store_is_rebuilt_from_the_migration_and_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'again.sqlite'}"
    assert db.init(url) == "0001_lifeos_core" and db.init(url) == "0001_lifeos_core"
    with db.session(url) as s:
        assert repo.list_for(s, "commitment", "nobody") == []


def test_a_foreign_key_is_enforced_and_children_are_deleted_with_their_parent():
    from sqlalchemy.exc import IntegrityError
    with db.session() as s:
        with pytest.raises(IntegrityError):
            repo.put(s, Commitment(id="orphan", person_id="nobody", title="x", start=T, deadline=T))
        s.rollback()
        repo.put(s, Person(id="eva"))
        repo.put(s, Commitment(id="c1", person_id="eva", title="x", start=T, deadline=T, requirements=["CV", "ID"]))
        assert repo.delete(s, "commitment", "c1")
        from sqlalchemy import text
        assert s.execute(text("select count(*) from commitment_requirements")).scalar() == 0


def test_the_contracts_are_served_over_http(client):
    client.put("/api/lifeos/persons", json={"id": "eva", "timezone": "Asia/Dhaka"})
    body = {"id": "c9", "person_id": "eva", "title": "Viva", "type": "exam", "location": {"name": "Shahbagh"}, "start": "2026-10-02T10:00:00+06:00", "deadline": "2026-10-02T10:00:00+06:00", "requirements": ["thesis"]}
    r = client.put("/api/lifeos/commitments", json=body)
    assert r.status_code == 200 and r.json()["deadline"].startswith("2026-10-02T04:00:00")
    assert client.get("/api/lifeos/commitment/c9").json()["requirements"] == ["thesis"]
    assert client.put("/api/lifeos/commitments", json={**body, "deadline": "2026-10-02T09:00:00+06:00"}).status_code == 422
    assert client.get("/api/lifeos/commitment?person_id=eva").json()[0]["id"] == "c9"
    assert "commitment" in client.get("/api/lifeos/schema").json()
    assert client.get("/api/lifeos/rocket/1").status_code == 404
    assert client.delete("/api/lifeos/commitment/c9").json() == {"deleted": "c9"}
