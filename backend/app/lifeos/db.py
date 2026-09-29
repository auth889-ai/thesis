"""THE AUTHORITATIVE STORE — one table per entity, SQLAlchemy 2.0, SQLite now and PostgreSQL later through the same
URL. Schema changes go through Alembic (backend/alembic); `init()` brings any database to the current head.
Rows hold the validated entity as JSON next to the columns the queries need, so the schema can grow without
losing what was stored."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import REPO

DEFAULT_URL = f"sqlite:///{(REPO / 'results/live/lifeos.sqlite').as_posix()}"


class Base(DeclarativeBase):
    pass


class _Row:
    id = Column(String, primary_key=True)
    person_id = Column(String, index=True)
    doc = Column(Text, nullable=False)                   # the validated entity, as JSON
    updated_at = Column(DateTime(timezone=True))


class PersonRow(Base, _Row):
    __tablename__ = "persons"; person_id = Column(String, index=True, nullable=True)


class CommitmentRow(Base, _Row):
    __tablename__ = "commitments"
    deadline = Column(DateTime(timezone=True), index=True); start = Column(DateTime(timezone=True)); type = Column(String); priority = Column(String)


class ConstraintRow(Base, _Row):
    __tablename__ = "constraints"; kind = Column(String)


class TravelEdgeRow(Base, _Row):
    __tablename__ = "travel_edges"; depart = Column(DateTime(timezone=True), index=True); mode = Column(String); duration_s = Column(Float); freshness = Column(String)


class OutcomeRow(Base, _Row):
    __tablename__ = "outcomes"; commitment_id = Column(String, index=True)


class ActionRow(Base, _Row):
    __tablename__ = "actions"; tool = Column(String); decision = Column(String); goal_id = Column(String, index=True)


class EventRow(Base, _Row):
    __tablename__ = "events"; kind = Column(String, index=True); occurred_at = Column(DateTime(timezone=True), index=True)


TABLES = {"person": PersonRow, "commitment": CommitmentRow, "constraint": ConstraintRow, "travel_edge": TravelEdgeRow, "outcome": OutcomeRow, "action": ActionRow, "event": EventRow}

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
            def _pragmas(conn, _):                          # noqa: ANN001 - SQLite: safe concurrent reads, durable writes
                conn.execute("pragma journal_mode=wal"); conn.execute("pragma foreign_keys=on")
        _engines[u] = e
    return _engines[u]


def init(db_url: str | None = None) -> str:
    """Bring the database to the current Alembic head; returns the revision. Safe to call at every start."""
    from alembic import command
    from alembic.config import Config
    u = db_url or url()
    cfg = Config(str(REPO / "backend/alembic.ini")); cfg.set_main_option("script_location", str(REPO / "backend/alembic")); cfg.set_main_option("sqlalchemy.url", u)
    command.upgrade(cfg, "head")
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(cfg).get_current_head() or ""


def session(db_url: str | None = None) -> Session:
    return sessionmaker(bind=engine(db_url), expire_on_commit=False, future=True)()


def dumps(obj) -> str:
    return json.dumps(obj.model_dump(mode="json"), sort_keys=True)
