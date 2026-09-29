"""Reads and writes: a validated entity in, rows out, and back. Child tables (requirements, dependencies, constraint
params and targets) and places are written with their parent; every function takes a session so a request, a test or a
job owns its own transaction."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.lifeos import db
from app.lifeos.entities import Action, Commitment, CommitmentType, Constraint, ConstraintKind, Event, EventKind, Flexibility, Freshness, MobilityProfile, Mode, Outcome, Person, Place, Priority, TravelEdge, Uncertainty

_now = lambda: datetime.now(timezone.utc)  # noqa: E731


# ------------------------------------------------------------------ places (shared by persons, commitments, edges)
def _place_id(person_id: str, p: Place) -> str:
    """One row per place name per person: 'Mirpur' typed twice is the same place; coordinates refine it, not duplicate it."""
    return p.id or "pl_" + hashlib.sha1(f"{person_id}|{' '.join(p.name.split()).lower()}".encode()).hexdigest()[:14]


def upsert_place(s: Session, person_id: str, p: Place | None) -> db.PlaceRow | None:
    if p is None:
        return None
    pid = _place_id(person_id, p)
    row = s.get(db.PlaceRow, pid) or db.PlaceRow(id=pid, person_id=person_id)
    row.name = p.name; row.lat = p.lat if p.lat is not None else row.lat; row.lng = p.lng if p.lng is not None else row.lng
    row.kind = p.kind if p.kind != "other" or not row.kind else row.kind
    s.add(row); s.flush(); return row


def _place(row: db.PlaceRow | None) -> Place | None:
    return Place(id=row.id, name=row.name, lat=row.lat, lng=row.lng, kind=row.kind) if row else None


# ------------------------------------------------------------------ persons
def put_person(s: Session, p: Person) -> Person:
    row = s.get(db.PersonRow, p.id) or db.PersonRow(id=p.id, created_at=_now())
    row.name, row.timezone, row.city, row.on_time_target, row.calibration_factor = p.name, p.timezone, p.city, p.on_time_target, p.calibration_factor
    row.max_walk_min, row.wheelchair, row.avoid_stairs, row.elevator_required = p.mobility.max_walk_min, p.mobility.wheelchair, p.mobility.avoid_stairs, p.mobility.elevator_required
    row.updated_at = _now(); s.add(row); s.flush()
    home = upsert_place(s, p.id, p.home.model_copy(update={"kind": "home"}) if p.home else None)
    row.home_place_id = home.id if home else None
    for pl in p.places:
        upsert_place(s, p.id, pl)
    s.commit(); return get_person(s, p.id)


def get_person(s: Session, id: str) -> Person | None:
    row = s.get(db.PersonRow, id, options=[selectinload(db.PersonRow.places)])
    if not row:
        return None
    home = next((_place(x) for x in row.places if x.id == row.home_place_id), None)
    return Person(id=row.id, name=row.name, timezone=row.timezone, city=row.city, home=home, places=[_place(x) for x in row.places if x.id != row.home_place_id],
                  mobility=MobilityProfile(max_walk_min=row.max_walk_min, wheelchair=row.wheelchair, avoid_stairs=row.avoid_stairs, elevator_required=row.elevator_required),
                  on_time_target=row.on_time_target, calibration_factor=row.calibration_factor)


# ------------------------------------------------------------------ commitments
def put_commitment(s: Session, c: Commitment) -> Commitment:
    row = s.get(db.CommitmentRow, c.id) or db.CommitmentRow(id=c.id, created_at=c.created_at)
    place = upsert_place(s, c.person_id, c.location)
    row.person_id, row.title, row.type, row.place_id = c.person_id, c.title, c.type.value, place.id if place else None
    row.start, row.deadline, row.duration_min, row.priority, row.flexibility = c.start, c.deadline, c.duration_min, c.priority.value, c.flexibility.value
    row.window_start, row.window_end, row.source, row.updated_at = c.window_start, c.window_end, c.source, _now()
    row.requirements = [db.RequirementRow(position=i, item=x) for i, x in enumerate(c.requirements)]
    row.dependencies = [db.DependencyRow(depends_on_id=d) for d in c.depends_on]
    s.add(row); s.commit(); return get_commitment(s, c.id)


def _commitment(row: db.CommitmentRow) -> Commitment:
    return Commitment(id=row.id, person_id=row.person_id, title=row.title, type=CommitmentType(row.type), location=_place(row.place), start=row.start, deadline=row.deadline,
                      duration_min=row.duration_min, priority=Priority(row.priority), flexibility=Flexibility(row.flexibility), window_start=row.window_start, window_end=row.window_end,
                      requirements=[r.item for r in row.requirements], depends_on=[d.depends_on_id for d in row.dependencies], source=row.source, created_at=row.created_at)


_C_LOAD = [selectinload(db.CommitmentRow.requirements), selectinload(db.CommitmentRow.dependencies), selectinload(db.CommitmentRow.place)]


def get_commitment(s: Session, id: str) -> Commitment | None:
    row = s.get(db.CommitmentRow, id, options=_C_LOAD)
    return _commitment(row) if row else None


def commitments_between(s: Session, person_id: str, start: datetime, end: datetime) -> list[Commitment]:
    """Commitments whose deadline falls in [start, end), earliest first: the day's spine."""
    q = select(db.CommitmentRow).options(*_C_LOAD).where(db.CommitmentRow.person_id == person_id, db.CommitmentRow.deadline >= start, db.CommitmentRow.deadline < end).order_by(db.CommitmentRow.deadline)
    return [_commitment(r) for r in s.execute(q).scalars().all()]


# ------------------------------------------------------------------ constraints
def put_constraint(s: Session, c: Constraint) -> Constraint:
    row = s.get(db.ConstraintRow, c.id) or db.ConstraintRow(id=c.id, created_at=c.created_at)
    row.person_id, row.kind, row.severity, row.source = c.person_id, c.kind.value, c.severity, c.source
    row.params = [db.ConstraintParamRow(key=k, value=str(v)) for k, v in c.params.items()]
    row.targets = [db.ConstraintTargetRow(target_id=t) for t in c.applies_to]
    s.add(row); s.commit(); return get_constraint(s, c.id)


def _cast(v: str):
    if v in ("True", "False"):
        return v == "True"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _constraint(row: db.ConstraintRow) -> Constraint:
    return Constraint(id=row.id, person_id=row.person_id, kind=ConstraintKind(row.kind), applies_to=[t.target_id for t in row.targets], params={p.key: _cast(p.value) for p in row.params}, severity=row.severity, source=row.source, created_at=row.created_at)


def get_constraint(s: Session, id: str) -> Constraint | None:
    row = s.get(db.ConstraintRow, id, options=[selectinload(db.ConstraintRow.params), selectinload(db.ConstraintRow.targets)])
    return _constraint(row) if row else None


# ------------------------------------------------------------------ travel edges
def put_edge(s: Session, t: TravelEdge) -> TravelEdge:
    row = s.get(db.TravelEdgeRow, t.id) or db.TravelEdgeRow(id=t.id)
    o, d = upsert_place(s, t.person_id, t.origin), upsert_place(s, t.person_id, t.destination)
    row.person_id, row.origin_place_id, row.destination_place_id, row.mode, row.depart = t.person_id, o.id, d.id, t.mode.value, t.depart
    row.duration_s, row.distance_m, row.cost, row.accessible, row.provider, row.model, row.freshness, row.generated_at = t.duration_s, t.distance_m, t.cost, t.accessible, t.provider, t.model, t.freshness.value, t.generated_at
    row.p10_s, row.p50_s, row.p90_s, row.uncertainty_method = t.uncertainty.p10_s, t.uncertainty.p50_s, t.uncertainty.p90_s, t.uncertainty.method
    s.add(row); s.commit(); return get_edge(s, t.id)


def _edge(row: db.TravelEdgeRow) -> TravelEdge:
    return TravelEdge(id=row.id, person_id=row.person_id, origin=_place(row.origin), destination=_place(row.destination), mode=Mode(row.mode), depart=row.depart, duration_s=row.duration_s, distance_m=row.distance_m,
                      uncertainty=Uncertainty(p10_s=row.p10_s, p50_s=row.p50_s, p90_s=row.p90_s, method=row.uncertainty_method), cost=row.cost, accessible=row.accessible,
                      provider=row.provider, model=row.model, freshness=Freshness(row.freshness), generated_at=row.generated_at)


def get_edge(s: Session, id: str) -> TravelEdge | None:
    row = s.get(db.TravelEdgeRow, id, options=[selectinload(db.TravelEdgeRow.origin), selectinload(db.TravelEdgeRow.destination)])
    return _edge(row) if row else None


# ------------------------------------------------------------------ outcomes, actions, events
def put_outcome(s: Session, o: Outcome) -> Outcome:
    row = s.get(db.OutcomeRow, o.id) or db.OutcomeRow(id=o.id)
    for k in ("person_id", "commitment_id", "planned_departure", "actual_departure", "predicted_arrival", "actual_arrival", "on_time", "forecast_error_s", "recorded_at"):
        setattr(row, k, getattr(o, k))
    s.add(row); s.commit(); return get_outcome(s, o.id)


def get_outcome(s: Session, id: str) -> Outcome | None:
    r = s.get(db.OutcomeRow, id)
    return Outcome(id=r.id, person_id=r.person_id, commitment_id=r.commitment_id, planned_departure=r.planned_departure, actual_departure=r.actual_departure, predicted_arrival=r.predicted_arrival, actual_arrival=r.actual_arrival, on_time=r.on_time, forecast_error_s=r.forecast_error_s, recorded_at=r.recorded_at) if r else None


def put_action(s: Session, a: Action) -> Action:
    row = s.get(db.ActionRow, a.id) or db.ActionRow(id=a.id)
    for k in ("person_id", "tool", "risk", "decision", "approved_by", "executed_at", "goal_id", "arguments", "result"):
        setattr(row, k, getattr(a, k))
    s.add(row); s.commit(); return get_action(s, a.id)


def get_action(s: Session, id: str) -> Action | None:
    r = s.get(db.ActionRow, id)
    return Action(id=r.id, person_id=r.person_id, tool=r.tool, arguments=r.arguments or {}, risk=r.risk, decision=r.decision, approved_by=r.approved_by, executed_at=r.executed_at, result=r.result, goal_id=r.goal_id) if r else None


def put_event(s: Session, e: Event) -> Event:
    row = s.get(db.EventRow, e.id) or db.EventRow(id=e.id)
    row.person_id, row.kind, row.occurred_at, row.source, row.payload = e.person_id, e.kind.value, e.occurred_at, e.source, e.payload
    s.add(row); s.commit(); return get_event(s, e.id)


def _event(r: db.EventRow) -> Event:
    return Event(id=r.id, person_id=r.person_id, kind=EventKind(r.kind), payload=r.payload or {}, occurred_at=r.occurred_at, source=r.source)


def get_event(s: Session, id: str) -> Event | None:
    r = s.get(db.EventRow, id)
    return _event(r) if r else None


def events_since(s: Session, since: datetime, person_id: str | None = None, limit: int = 200) -> list[Event]:
    q = select(db.EventRow).where(db.EventRow.occurred_at >= since)
    if person_id:
        q = q.where(db.EventRow.person_id == person_id)
    return [_event(r) for r in s.execute(q.order_by(db.EventRow.occurred_at).limit(limit)).scalars().all()]


# ------------------------------------------------------------------ generic access by kind (the routes)
_TABLE = {"person": db.PersonRow, "commitment": db.CommitmentRow, "constraint": db.ConstraintRow, "travel_edge": db.TravelEdgeRow, "outcome": db.OutcomeRow, "action": db.ActionRow, "event": db.EventRow}
_GET = {"person": get_person, "commitment": get_commitment, "constraint": get_constraint, "travel_edge": get_edge, "outcome": get_outcome, "action": get_action, "event": get_event}
_PUT = {Person: put_person, Commitment: put_commitment, Constraint: put_constraint, TravelEdge: put_edge, Outcome: put_outcome, Action: put_action, Event: put_event}


def put(s: Session, entity):
    return _PUT[type(entity)](s, entity)


def get(s: Session, kind: str, id: str):
    return _GET[kind](s, id)


def delete(s: Session, kind: str, id: str) -> bool:
    row = s.get(_TABLE[kind], id)
    if not row:
        return False
    s.delete(row); s.commit(); return True


def list_for(s: Session, kind: str, person_id: str, limit: int = 500):
    table = _TABLE[kind]
    if kind == "person":
        p = get_person(s, person_id); return [p] if p else []
    ids = s.execute(select(table.id).where(table.person_id == person_id).limit(limit)).scalars().all()
    return [_GET[kind](s, i) for i in ids]
