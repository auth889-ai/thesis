"""LIFE OS core relational schema: persons, places, commitments (+ requirements, dependencies), constraints (+ params, targets),
travel_edges, outcomes, actions, events

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


def upgrade() -> None:
    op.create_table("persons",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("name", sa.String(200)), sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("city", sa.String(200)), sa.Column("home_place_id", sa.String(64)),
        sa.Column("on_time_target", sa.Float(), nullable=False, server_default="0.8"), sa.Column("calibration_factor", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("max_walk_min", sa.Integer(), nullable=False, server_default="20"), sa.Column("wheelchair", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("avoid_stairs", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("elevator_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("places",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(300), nullable=False), sa.Column("lat", sa.Float()), sa.Column("lng", sa.Float()), sa.Column("kind", sa.String(32), nullable=False, server_default="other"))
    with op.batch_alter_table("persons") as b:
        b.create_foreign_key("fk_persons_home_place", "places", ["home_place_id"], ["id"], ondelete="SET NULL")
    op.create_table("commitments",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("type", sa.String(32), nullable=False, index=True),
        sa.Column("place_id", sa.String(64), sa.ForeignKey("places.id", ondelete="SET NULL")),
        sa.Column("start", sa.DateTime(timezone=True)), sa.Column("deadline", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="60"), sa.Column("priority", sa.String(16), nullable=False, index=True),
        sa.Column("flexibility", sa.String(32), nullable=False), sa.Column("window_start", sa.DateTime(timezone=True)), sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(32), nullable=False, server_default="person"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("commitment_requirements",
        sa.Column("commitment_id", sa.String(64), sa.ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True), sa.Column("item", sa.String(300), nullable=False))
    op.create_table("commitment_dependencies",
        sa.Column("commitment_id", sa.String(64), sa.ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on_id", sa.String(64), sa.ForeignKey("commitments.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("constraints",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(32), nullable=False, index=True), sa.Column("severity", sa.String(8), nullable=False, server_default="soft"),
        sa.Column("source", sa.String(32), nullable=False, server_default="person"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("constraint_params",
        sa.Column("constraint_id", sa.String(64), sa.ForeignKey("constraints.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True), sa.Column("value", sa.String(500), nullable=False))
    op.create_table("constraint_targets",
        sa.Column("constraint_id", sa.String(64), sa.ForeignKey("constraints.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_id", sa.String(64), primary_key=True))
    op.create_table("travel_edges",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("origin_place_id", sa.String(64), sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_place_id", sa.String(64), sa.ForeignKey("places.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, index=True), sa.Column("depart", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("duration_s", sa.Integer(), nullable=False), sa.Column("distance_m", sa.Integer()),
        sa.Column("p10_s", sa.Integer()), sa.Column("p50_s", sa.Integer()), sa.Column("p90_s", sa.Integer()), sa.Column("uncertainty_method", sa.String(32)),
        sa.Column("cost", sa.Float()), sa.Column("accessible", sa.Boolean()), sa.Column("provider", sa.String(64), nullable=False), sa.Column("model", sa.String(128)),
        sa.Column("freshness", sa.String(16), nullable=False, index=True), sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("outcomes",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("commitment_id", sa.String(64), sa.ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("planned_departure", sa.DateTime(timezone=True)), sa.Column("actual_departure", sa.DateTime(timezone=True)),
        sa.Column("predicted_arrival", sa.DateTime(timezone=True)), sa.Column("actual_arrival", sa.DateTime(timezone=True)),
        sa.Column("on_time", sa.Boolean()), sa.Column("forecast_error_s", sa.Integer()), sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("actions",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tool", sa.String(64), nullable=False, index=True), sa.Column("risk", sa.String(24), nullable=False), sa.Column("decision", sa.String(8), nullable=False, index=True),
        sa.Column("approved_by", sa.String(64)), sa.Column("executed_at", sa.DateTime(timezone=True)), sa.Column("goal_id", sa.String(64), index=True),
        sa.Column("arguments", sa.JSON(), nullable=False), sa.Column("result", sa.JSON()))
    op.create_table("events",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("person_id", sa.String(64), sa.ForeignKey("persons.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(32), nullable=False, index=True), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="system"), sa.Column("payload", sa.JSON(), nullable=False))


def downgrade() -> None:
    for t in ("events", "actions", "outcomes", "travel_edges", "constraint_targets", "constraint_params", "constraints", "commitment_dependencies", "commitment_requirements", "commitments"):
        op.drop_table(t)
    with op.batch_alter_table("persons") as b:
        b.drop_constraint("fk_persons_home_place", type_="foreignkey")
    op.drop_table("places"); op.drop_table("persons")
