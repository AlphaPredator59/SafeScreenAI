"""Alter evidence.content from VARCHAR(1024) to TEXT.

Revision ID: 20261008_0003
Revises: 20260823_0002
Create Date: 2026-10-08 11:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_0003"
down_revision: str | None = "20260823_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence") as batch_op:
        batch_op.alter_column(
            "content",
            existing_type=sa.String(length=1024),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence") as batch_op:
        batch_op.alter_column(
            "content",
            existing_type=sa.Text(),
            type_=sa.String(length=1024),
            existing_nullable=True,
        )
