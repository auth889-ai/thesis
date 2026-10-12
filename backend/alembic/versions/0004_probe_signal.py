"""The signal history on probe fixes and cells (Q3, works with weak signal): what the browser said about the network at each fix

Revision ID: 0004_probe_signal
Revises: 0003_road_watches
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_probe_signal"
down_revision = "0003_road_watches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("probe_points") as b:
        b.add_column(sa.Column("net_type", sa.String(12)))
        b.add_column(sa.Column("downlink_mbps", sa.Float()))
        b.add_column(sa.Column("rtt_ms", sa.Float()))
    with op.batch_alter_table("probe_cells") as b:
        b.add_column(sa.Column("n_signal", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("weak_signal", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("mean_downlink_mbps", sa.Float()))


def downgrade() -> None:
    with op.batch_alter_table("probe_cells") as b:
        b.drop_column("mean_downlink_mbps"); b.drop_column("weak_signal"); b.drop_column("n_signal")
    with op.batch_alter_table("probe_points") as b:
        b.drop_column("rtt_ms"); b.drop_column("downlink_mbps"); b.drop_column("net_type")
