"""Reads and writes of the seven entities: validate, store the JSON with its query columns, read back as the entity.
The functions take a session so a request, a test or a job can each own its transaction."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lifeos import db
from app.lifeos.entities import ENTITIES, Action, Commitment, Constraint, Event, Outcome, Person, TravelEdge

_COLUMNS = {
    "commitment": lambda c: {"deadline": c.deadline, "start": c.start, "type": c.type.value, "priority": c.priority.value},
    "constraint": lambda c: {"kind": c.kind.value},
    "travel_edge": lambda t: {"depart": t.depart, "mode": t.mode.value, "duration_s": t.duration_s, "freshness": t.freshness.value},
    "outcome": lambda o: {"commitment_id": o.commitment_id},
    "action": lambda a: {"tool": a.tool, "decision": a.decision, "goal_id": a.goal_id},
    "event": lambda e: {"kind": e.kind.value, "occurred_at": e.occurred_at},
    "person": lambda p: {},
}


def _kind(entity: BaseModel) -> str:
    return next(k for k, cls in ENTITIES.items() if isinstance(entity, cls))


def put(s: Session, entity: BaseModel) -> BaseModel:
    """Insert or replace; the entity is validated already by being an instance."""
    kind = _kind(entity); row_cls = db.TABLES[kind]
    row = s.get(row_cls, entity.id) or row_cls(id=entity.id)
    row.person_id = getattr(entity, "person_id", None) if kind != "person" else entity.id
    row.doc = db.dumps(entity); row.updated_at = datetime.now(timezone.utc)
    for k, v in _COLUMNS[kind](entity).items():
        setattr(row, k, v)
    s.add(row); s.commit()
    return entity


def get(s: Session, kind: str, id: str) -> BaseModel | None:
    row = s.get(db.TABLES[kind], id)
    return ENTITIES[kind].model_validate_json(row.doc) if row else None


def delete(s: Session, kind: str, id: str) -> bool:
    row = s.get(db.TABLES[kind], id)
    if not row:
        return False
    s.delete(row); s.commit(); return True


def list_for(s: Session, kind: str, person_id: str, limit: int = 500) -> list[BaseModel]:
    row_cls = db.TABLES[kind]
    col = row_cls.id if kind == "person" else row_cls.person_id
    rows = s.execute(select(row_cls).where(col == person_id).limit(limit)).scalars().all()
    return [ENTITIES[kind].model_validate_json(r.doc) for r in rows]


def commitments_between(s: Session, person_id: str, start: datetime, end: datetime) -> list[Commitment]:
    """Commitments whose deadline falls in [start, end), earliest first: the day's spine."""
    rows = s.execute(select(db.CommitmentRow).where(db.CommitmentRow.person_id == person_id, db.CommitmentRow.deadline >= start, db.CommitmentRow.deadline < end).order_by(db.CommitmentRow.deadline)).scalars().all()
    return [Commitment.model_validate_json(r.doc) for r in rows]


def events_since(s: Session, since: datetime, person_id: str | None = None, limit: int = 200) -> list[Event]:
    q = select(db.EventRow).where(db.EventRow.occurred_at >= since)
    if person_id:
        q = q.where(db.EventRow.person_id == person_id)
    rows = s.execute(q.order_by(db.EventRow.occurred_at).limit(limit)).scalars().all()
    return [Event.model_validate_json(r.doc) for r in rows]


__all__ = ["put", "get", "delete", "list_for", "commitments_between", "events_since", "Person", "Commitment", "Constraint", "TravelEdge", "Outcome", "Action", "Event"]
