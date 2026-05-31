"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("api_token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_candidates_email", "candidates", ["email"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_experience_years", sa.Integer(), server_default="0"),
        sa.Column("technical_skills", postgresql.JSONB(), server_default="[]"),
        sa.Column("salary_min", sa.Numeric(12, 2)),
        sa.Column("salary_max", sa.Numeric(12, 2)),
        sa.Column("location", sa.String(255)),
        sa.Column("job_url", sa.String(512)),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("embedding", Vector(_DIM)),
        sa.Column("work_model", sa.String(20), server_default="on-site"),
        sa.Column("is_remote", sa.Boolean(), server_default=sa.false()),
        sa.Column("industry", sa.String(100)),
        sa.Column("company_rating", sa.Numeric(3, 2)),
        sa.Column("company_size", sa.String(50)),
        sa.Column("job_type", sa.String(30), server_default="full-time"),
        sa.Column("posted_date", sa.DateTime(timezone=True)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source", "source_id", name="uq_job_source_id"),
    )
    op.create_index("ix_jobs_company", "jobs", ["company"])
    op.create_index("idx_job_active_scraped", "jobs", ["is_active", "scraped_at"])
    op.create_index("idx_job_work_model", "jobs", ["work_model"])
    op.create_index("idx_job_industry", "jobs", ["industry"])
    op.create_index("idx_job_type", "jobs", ["job_type"])
    op.execute(
        "CREATE INDEX idx_job_embedding_hnsw ON jobs "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 24, ef_construction = 200)"
    )

    op.create_table(
        "job_boards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.String(512)),
        sa.Column("category", sa.String(50), server_default="general"),
        sa.Column("is_premium", sa.Boolean(), server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_job_board_name"),
    )

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("raw_text", sa.Text()),
        sa.Column("parsed_data", postgresql.JSONB()),
        sa.Column("embedding", Vector(_DIM)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_resumes_candidate_id", "resumes", ["candidate_id"])
    op.create_index("ix_resumes_content_hash", "resumes", ["content_hash"])
    op.execute(
        "CREATE INDEX idx_resume_embedding_hnsw ON resumes "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 24, ef_construction = 200)"
    )

    op.create_table(
        "job_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column("semantic_similarity", sa.Numeric(5, 2)),
        sa.Column("skill_match_percentage", sa.Numeric(5, 2)),
        sa.Column("matched_skills", postgresql.JSONB()),
        sa.Column("reasoning", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("resume_id", "job_id", name="uq_resume_job_match"),
    )
    op.create_index("ix_job_matches_resume_id", "job_matches", ["resume_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])
    op.create_index("idx_match_resume_score", "job_matches", ["resume_id", "match_score"])

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filters", postgresql.JSONB(), server_default="{}"),
        sa.Column("min_score", sa.Numeric(5, 2), server_default="0"),
        sa.Column("frequency", sa.String(10), server_default="daily"),
        sa.Column("channel", sa.String(10), server_default="email"),
        sa.Column("destination", sa.String(512)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_subscriptions_candidate_id", "subscriptions", ["candidate_id"])
    op.create_index("idx_subscription_active_freq", "subscriptions", ["is_active", "frequency"])

    op.create_table(
        "alert_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_ids", postgresql.JSONB(), server_default="[]"),
        sa.Column("match_count", sa.Integer(), server_default="0"),
        sa.Column("channel", sa.String(10)),
        sa.Column("status", sa.String(10), server_default="sent"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alert_deliveries_subscription_id", "alert_deliveries", ["subscription_id"])


def downgrade() -> None:
    op.drop_table("alert_deliveries")
    op.drop_table("subscriptions")
    op.drop_table("job_matches")
    op.drop_table("resumes")
    op.drop_table("job_boards")
    op.drop_table("jobs")
    op.drop_index("ix_candidates_email", table_name="candidates")
    op.drop_table("candidates")
