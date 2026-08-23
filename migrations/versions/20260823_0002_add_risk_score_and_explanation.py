"""Add risk_score and explanation to moderation_results.

Revision ID: 20260823_0002
Revises: 20260821_0001
Create Date: 2026-08-23 17:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260823_0002"
down_revision: str | None = "20260821_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("moderation_results") as batch_op:
        batch_op.add_column(sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("explanation", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_moderation_results_risk_score_range",
            "risk_score >= 0 AND risk_score <= 1",
        )


def downgrade() -> None:
    with op.batch_alter_table("moderation_results") as batch_op:
        batch_op.drop_constraint("ck_moderation_results_risk_score_range", type_="check")
        batch_op.drop_column("explanation")
        batch_op.drop_column("risk_score")
