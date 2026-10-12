"""Relational tables for probes, on the core store's metadata and migration chain.

probe_points   one row per shared location fix, raw and snapped; purged after RETAIN_HOURS
probe_cells    one row per (cell, 5-minute bin): the aggregate the map shows; kept
A cell is an H3 hexagon (resolution 10, about 70 m across) plus a heading octant, so the two directions
of one road are two cells. It is named a cell, not a road: no map-matching to a named way is claimed.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.lifeos.db import UTC, Base

RETAIN_HOURS = 24
H3_RES = 10


class ProbePointRow(Base):
    __tablename__ = "probe_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device: Mapped[str] = mapped_column(String(16), index=True)                 # sha256 of the browser id, first 16 hex
    city: Mapped[str] = mapped_column(String(64), index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTC, index=True)
    received_at: Mapped[datetime] = mapped_column(UTC)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)                     # from the device, or derived from the previous fix
    net_type: Mapped[str | None] = mapped_column(String(12))                   # the signal history: navigator.connection.effectiveType, when the device gave it
    downlink_mbps: Mapped[float | None] = mapped_column(Float)
    rtt_ms: Mapped[float | None] = mapped_column(Float)
    snapped_lat: Mapped[float | None] = mapped_column(Float)
    snapped_lng: Mapped[float | None] = mapped_column(Float)
    snap_confidence: Mapped[float | None] = mapped_column(Float)
    snapper: Mapped[str] = mapped_column(String(32), default="none")          # valhalla | amazon_location | none
    cell: Mapped[str | None] = mapped_column(String(32), index=True)


class ProbeCellRow(Base):
    __tablename__ = "probe_cells"
    cell: Mapped[str] = mapped_column(String(32), primary_key=True)
    bin_start: Mapped[datetime] = mapped_column(UTC, primary_key=True)
    city: Mapped[str] = mapped_column(String(64), index=True)
    lat: Mapped[float] = mapped_column(Float)                                   # cell centre
    lng: Mapped[float] = mapped_column(Float)
    n_points: Mapped[int] = mapped_column(Integer, default=0)
    n_devices: Mapped[int] = mapped_column(Integer, default=0)
    mean_speed_kmh: Mapped[float | None] = mapped_column(Float)
    p50_speed_kmh: Mapped[float | None] = mapped_column(Float)
    n_signal: Mapped[int] = mapped_column(Integer, default=0)                   # fixes in this bin that carried a signal reading
    weak_signal: Mapped[int] = mapped_column(Integer, default=0)                # of those, how many were slow-2g / 2g or under 0.5 Mbit/s
    mean_downlink_mbps: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(UTC)
