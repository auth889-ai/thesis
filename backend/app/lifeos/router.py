"""LIFE OS core routes: create, read, list and delete each entity; the contracts are the request and response bodies."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.lifeos import db, repo
from app.lifeos.entities import ENTITIES, Action, Commitment, Constraint, Event, Outcome, Person, TravelEdge

router = APIRouter(prefix="/api/lifeos", tags=["lifeos"])
_KINDS = ", ".join(ENTITIES)


def _kind(kind: str) -> str:
    if kind not in ENTITIES:
        raise HTTPException(404, f"unknown entity kind {kind!r}; one of {_KINDS}")
    return kind


@router.get("/schema")
def schema():
    """The contracts as JSON Schema, for clients and for the model."""
    return {k: cls.model_json_schema() for k, cls in ENTITIES.items()}


@router.put("/persons")
def put_person(p: Person):
    with db.session() as s:
        return repo.put(s, p)


@router.put("/commitments")
def put_commitment(c: Commitment):
    with db.session() as s:
        return repo.put(s, c)


@router.put("/constraints")
def put_constraint(c: Constraint):
    with db.session() as s:
        return repo.put(s, c)


@router.put("/travel-edges")
def put_edge(t: TravelEdge):
    with db.session() as s:
        return repo.put(s, t)


@router.put("/outcomes")
def put_outcome(o: Outcome):
    with db.session() as s:
        return repo.put(s, o)


@router.put("/actions")
def put_action(a: Action):
    with db.session() as s:
        return repo.put(s, a)


@router.put("/events")
def put_event(e: Event):
    with db.session() as s:
        return repo.put(s, e)


@router.get("/{kind}/{id}")
def get_one(kind: str, id: str):
    with db.session() as s:
        e = repo.get(s, _kind(kind), id)
    if not e:
        raise HTTPException(404, f"no {kind} {id}")
    return e


@router.delete("/{kind}/{id}")
def delete_one(kind: str, id: str):
    with db.session() as s:
        if not repo.delete(s, _kind(kind), id):
            raise HTTPException(404, f"no {kind} {id}")
    return {"deleted": id}


@router.get("/{kind}")
def list_kind(kind: str, person_id: str, since: datetime | None = None, until: datetime | None = None):
    k = _kind(kind)
    with db.session() as s:
        if k == "commitment" and since and until:
            return repo.commitments_between(s, person_id, since.astimezone(timezone.utc), until.astimezone(timezone.utc))
        if k == "event" and since:
            return repo.events_since(s, since.astimezone(timezone.utc), person_id)
        return repo.list_for(s, k, person_id)
