"""Relational tables for road watches and the alerts raised on them, on the core store's migration chain."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.lifeos.db import UTC, Base


class RoadWatchRow(Base):
    __tablename__ = "road_watches"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset: Mapped[str] = mapped_column(String(64), index=True)
    node: Mapped[str] = mapped_column(String(32))
    label: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTC)


class RoadAlertRow(Base):
    __tablename__ = "road_alerts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("road_watches.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[int] = mapped_column(Integer, index=True)
    model: Mapped[str] = mapped_column(String(32))
    horizon_min: Mapped[int] = mapped_column(Integer)
    now_speed: Mapped[float] = mapped_column(Float)
    predicted_speed: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTC)
