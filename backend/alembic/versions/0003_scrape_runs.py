"""add scrape_runs ledger (paid-scrape weekly guard + cost visibility)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-20

A new standalone table — no data backfill, no locking concern.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("companies", postgresql.JSONB(), server_default="[]"),
        sa.Column("returned", sa.Integer(), server_default="0"),
        sa.Column("inserted", sa.Integer(), server_default="0"),
        sa.Column("updated", sa.Integer(), server_default="0"),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scrape_runs_tier", "scrape_runs", ["tier"])
    op.create_index("ix_scrape_runs_run_at", "scrape_runs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_scrape_runs_run_at", table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_tier", table_name="scrape_runs")
    op.drop_table("scrape_runs")
