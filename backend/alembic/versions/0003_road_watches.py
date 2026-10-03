"""Road watches and the onset alerts raised on them

Revision ID: 0003_road_watches
Revises: 0002_probes
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_road_watches"
down_revision = "0002_probes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("road_watches",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), nullable=False, index=True),
        sa.Column("dataset", sa.String(64), nullable=False, index=True), sa.Column("node", sa.String(32), nullable=False),
        sa.Column("label", sa.String(200)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("road_alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("watch_id", sa.String(64), sa.ForeignKey("road_watches.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("as_of", sa.Integer(), nullable=False, index=True), sa.Column("model", sa.String(32), nullable=False),
        sa.Column("horizon_min", sa.Integer(), nullable=False), sa.Column("now_speed", sa.Float(), nullable=False),
        sa.Column("predicted_speed", sa.Float(), nullable=False), sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("road_alerts")
    op.drop_table("road_watches")
