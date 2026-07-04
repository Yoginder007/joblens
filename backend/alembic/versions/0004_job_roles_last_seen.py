"""job role taxonomy + last_seen freshness; drop fabricated metadata defaults

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04

- ``role_category``: taxonomy bucket derived from the title at ingestion.
- ``last_seen_at``: most recent scrape that still returned the posting.
  Backfilled from ``scraped_at`` so freshness filters keep working.
- ``job_type`` becomes nullable and the historically hardcoded values are
  nulled out: every existing row was stamped "full-time" by the old
  ``_normalize`` regardless of reality (same for industry="Tech" and
  company_size="1000+"), which made those filters decorative. NULL = unknown;
  the next ingest run re-fills them from real source data where available.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("role_category", sa.String(40), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("last_seen_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("idx_job_role_category", "jobs", ["role_category"])
    op.create_index("idx_job_last_seen", "jobs", ["last_seen_at"])

    op.execute("UPDATE jobs SET last_seen_at = scraped_at WHERE last_seen_at IS NULL")

    op.alter_column("jobs", "job_type", existing_type=sa.String(30), nullable=True)
    # Null out the fabricated constants (unknown ≠ made up).
    op.execute("UPDATE jobs SET job_type = NULL WHERE job_type = 'full-time'")
    op.execute("UPDATE jobs SET industry = NULL WHERE industry = 'Tech'")
    op.execute("UPDATE jobs SET company_size = NULL WHERE company_size = '1000+'")


def downgrade() -> None:
    op.execute("UPDATE jobs SET job_type = 'full-time' WHERE job_type IS NULL")
    op.alter_column("jobs", "job_type", existing_type=sa.String(30), nullable=False)
    op.drop_index("idx_job_last_seen", table_name="jobs")
    op.drop_index("idx_job_role_category", table_name="jobs")
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "role_category")
