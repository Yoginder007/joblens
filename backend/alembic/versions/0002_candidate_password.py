"""add nullable password_hash to candidates

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-06

Adding a NULLABLE column is a safe, non-locking change on Postgres — existing
rows (guest/legacy candidates) keep working with password_hash = NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "password_hash")
