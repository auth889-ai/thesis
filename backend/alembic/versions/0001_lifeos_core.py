"""LIFE OS core: persons, commitments, constraints, travel_edges, outcomes, actions, events (Phase 0 contracts)

Revision ID: 0001_lifeos_core
Revises:
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_lifeos_core"
down_revision = None
branch_labels = None
depends_on = None

_common = lambda: [sa.Column("id", sa.String(), primary_key=True), sa.Column("person_id", sa.String(), index=True), sa.Column("doc", sa.Text(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True))]  # noqa: E731


def upgrade() -> None:
    op.create_table("persons", *_common())
    op.create_table("commitments", *_common(), sa.Column("deadline", sa.DateTime(timezone=True), index=True), sa.Column("start", sa.DateTime(timezone=True)), sa.Column("type", sa.String()), sa.Column("priority", sa.String()))
    op.create_table("constraints", *_common(), sa.Column("kind", sa.String()))
    op.create_table("travel_edges", *_common(), sa.Column("depart", sa.DateTime(timezone=True), index=True), sa.Column("mode", sa.String()), sa.Column("duration_s", sa.Float()), sa.Column("freshness", sa.String()))
    op.create_table("outcomes", *_common(), sa.Column("commitment_id", sa.String(), index=True))
    op.create_table("actions", *_common(), sa.Column("tool", sa.String()), sa.Column("decision", sa.String()), sa.Column("goal_id", sa.String(), index=True))
    op.create_table("events", *_common(), sa.Column("kind", sa.String(), index=True), sa.Column("occurred_at", sa.DateTime(timezone=True), index=True))


def downgrade() -> None:
    for t in ("events", "actions", "outcomes", "travel_edges", "constraints", "commitments", "persons"):
        op.drop_table(t)
