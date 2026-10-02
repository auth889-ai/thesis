"""THE AUTHORITATIVE STORE — a relational schema, one column per field, foreign keys between entities.
SQLAlchemy 2.0 declarative; SQLite now, PostgreSQL through the same URL; schema changes only through Alembic.
The two payloads that are free-form by nature (a tool call's arguments and result, an event's payload) are JSON
columns, which PostgreSQL stores as jsonb; everything with a defined shape is a column or a child table."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, TypeDecorator, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.paths import REPO

DEFAULT_URL = f"sqlite:///{(REPO / 'results/live/lifeos.sqlite').as_posix()}"


class UTC(TypeDecorator):
    """A timestamp stored in UTC and read back timezone-aware on every database (SQLite drops the offset otherwise)."""
    impl = DateTime(timezone=True); cache_ok = True

    def process_bind_param(self, value, dialect):
        from datetime import timezone
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        from datetime import timezone
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class Base(DeclarativeBase):
    pass


class PersonRow(Base):
    __tablename__ = "persons"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    city: Mapped[str | None] = mapped_column(String(200))
    home_place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    on_time_target: Mapped[float] = mapped_column(Float, default=0.8)
    calibration_factor: Mapped[float] = mapped_column(Float, default=1.0)
    max_walk_min: Mapped[int] = mapped_column(Integer, default=20)
    wheelchair: Mapped[bool] = mapped_column(Boolean, default=False)
    avoid_stairs: Mapped[bool] = mapped_column(Boolean, default=False)
    elevator_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTC)
    updated_at: Mapped[datetime] = mapped_column(UTC)
    places: Mapped[list["PlaceRow"]] = relationship(back_populates="person", foreign_keys="PlaceRow.person_id", cascade="all, delete-orphan")


class PlaceRow(Base):
    __tablename__ = "places"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(32), default="other")          # home | work | saved | other
    person: Mapped["PersonRow"] = relationship(back_populates="places", foreign_keys=[person_id])


class CommitmentRow(Base):
    __tablename__ = "commitments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(32), index=True)
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    start: Mapped[datetime | None] = mapped_column(UTC)
    deadline: Mapped[datetime] = mapped_column(UTC, index=True)
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    priority: Mapped[str] = mapped_column(String(16), index=True)
    flexibility: Mapped[str] = mapped_column(String(32))
    window_start: Mapped[datetime | None] = mapped_column(UTC)
    window_end: Mapped[datetime | None] = mapped_column(UTC)
    source: Mapped[str] = mapped_column(String(32), default="person")
    created_at: Mapped[datetime] = mapped_column(UTC)
    updated_at: Mapped[datetime] = mapped_column(UTC)
    place: Mapped["PlaceRow | None"] = relationship(foreign_keys=[place_id])
    requirements: Mapped[list["RequirementRow"]] = relationship(cascade="all, delete-orphan", order_by="RequirementRow.position")
    dependencies: Mapped[list["DependencyRow"]] = relationship(cascade="all, delete-orphan", foreign_keys="DependencyRow.commitment_id")


class RequirementRow(Base):
    __tablename__ = "commitment_requirements"
    commitment_id: Mapped[str] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    item: Mapped[str] = mapped_column(String(300))


class DependencyRow(Base):
    __tablename__ = "commitment_dependencies"
    commitment_id: Mapped[str] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True)


class ConstraintRow(Base):
    __tablename__ = "constraints"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(8), default="soft")
    source: Mapped[str] = mapped_column(String(32), default="person")
    created_at: Mapped[datetime] = mapped_column(UTC)
    params: Mapped[list["ConstraintParamRow"]] = relationship(cascade="all, delete-orphan")
    targets: Mapped[list["ConstraintTargetRow"]] = relationship(cascade="all, delete-orphan")


class ConstraintParamRow(Base):
    __tablename__ = "constraint_params"
    constraint_id: Mapped[str] = mapped_column(ForeignKey("constraints.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))                           # text; the entity casts back by key


class ConstraintTargetRow(Base):
    __tablename__ = "constraint_targets"
    constraint_id: Mapped[str] = mapped_column(ForeignKey("constraints.id", ondelete="CASCADE"), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(64), primary_key=True)       # a commitment id or a travel edge id


class TravelEdgeRow(Base):
    __tablename__ = "travel_edges"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    origin_place_id: Mapped[str] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    destination_place_id: Mapped[str] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(16), index=True)
    depart: Mapped[datetime] = mapped_column(UTC, index=True)
    duration_s: Mapped[int] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    p10_s: Mapped[int | None] = mapped_column(Integer); p50_s: Mapped[int | None] = mapped_column(Integer); p90_s: Mapped[int | None] = mapped_column(Integer)
    uncertainty_method: Mapped[str | None] = mapped_column(String(32))
    cost: Mapped[float | None] = mapped_column(Float)
    accessible: Mapped[bool | None] = mapped_column(Boolean)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    freshness: Mapped[str] = mapped_column(String(16), index=True)
    generated_at: Mapped[datetime] = mapped_column(UTC)
    origin: Mapped["PlaceRow"] = relationship(foreign_keys=[origin_place_id])
    destination: Mapped["PlaceRow"] = relationship(foreign_keys=[destination_place_id])


class OutcomeRow(Base):
    __tablename__ = "outcomes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    commitment_id: Mapped[str] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), index=True)
    planned_departure: Mapped[datetime | None] = mapped_column(UTC)
    actual_departure: Mapped[datetime | None] = mapped_column(UTC)
    predicted_arrival: Mapped[datetime | None] = mapped_column(UTC)
    actual_arrival: Mapped[datetime | None] = mapped_column(UTC)
    on_time: Mapped[bool | None] = mapped_column(Boolean)
    forecast_error_s: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(UTC)


class ActionRow(Base):
    __tablename__ = "actions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(64), index=True)
    risk: Mapped[str] = mapped_column(String(24))
    decision: Mapped[str] = mapped_column(String(8), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(64))
    executed_at: Mapped[datetime | None] = mapped_column(UTC)
    goal_id: Mapped[str | None] = mapped_column(String(64), index=True)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)               # free-form by nature: each tool has its own arguments
    result: Mapped[dict | None] = mapped_column(JSON)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTC, index=True)
    source: Mapped[str] = mapped_column(String(32), default="system")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)                 # free-form by nature: each event kind carries its own facts


_engines: dict[str, object] = {}


def url() -> str:
    return os.environ.get("LIFEOS_DATABASE_URL", DEFAULT_URL)


def engine(db_url: str | None = None):
    u = db_url or url()
    if u not in _engines:
        if u.startswith("sqlite:///"):
            Path(u.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        e = create_engine(u, future=True, connect_args={"check_same_thread": False} if u.startswith("sqlite") else {})
        if u.startswith("sqlite"):
            @event.listens_for(e, "connect")
            def _pragmas(conn, _):                          # noqa: ANN001 - SQLite: durable writes, enforced foreign keys
                conn.execute("pragma journal_mode=wal"); conn.execute("pragma foreign_keys=on")
        _engines[u] = e
    return _engines[u]


def init(db_url: str | None = None) -> str:
    """Bring the database to the current Alembic head; returns the revision. Safe to call at every start."""
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    u = db_url or url()
    cfg = Config(str(REPO / "backend/alembic.ini")); cfg.set_main_option("script_location", str(REPO / "backend/alembic")); cfg.set_main_option("sqlalchemy.url", u)
    command.upgrade(cfg, "head")
    return ScriptDirectory.from_config(cfg).get_current_head() or ""


def session(db_url: str | None = None) -> Session:
    return sessionmaker(bind=engine(db_url), expire_on_commit=False, future=True)()


def _register_domains() -> None:
    """Other domains' tables live on this metadata so one migration chain owns the database."""
    import app.probes.db  # noqa: F401


_register_domains()
