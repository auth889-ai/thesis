"""Probes: probe_points (raw and snapped fixes, purged) and probe_cells (per cell and 5-minute bin)

Revision ID: 0002_probes
Revises: 0001_lifeos_core
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_probes"
down_revision = "0001_lifeos_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("probe_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device", sa.String(16), nullable=False, index=True), sa.Column("city", sa.String(64), nullable=False, index=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, index=True), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False), sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float()), sa.Column("heading", sa.Float()), sa.Column("speed_kmh", sa.Float()),
        sa.Column("snapped_lat", sa.Float()), sa.Column("snapped_lng", sa.Float()), sa.Column("snap_confidence", sa.Float()),
        sa.Column("snapper", sa.String(32), nullable=False, server_default="none"), sa.Column("cell", sa.String(32), index=True))
    op.create_table("probe_cells",
        sa.Column("cell", sa.String(32), primary_key=True), sa.Column("bin_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("city", sa.String(64), nullable=False, index=True), sa.Column("lat", sa.Float(), nullable=False), sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("n_points", sa.Integer(), nullable=False, server_default="0"), sa.Column("n_devices", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mean_speed_kmh", sa.Float()), sa.Column("p50_speed_kmh", sa.Float()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("probe_cells")
    op.drop_table("probe_points")
