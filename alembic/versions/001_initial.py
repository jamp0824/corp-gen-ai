"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrichment_jobs",
        sa.Column("id",              sa.String(36),   primary_key=True),
        sa.Column("company_id",      sa.String(100),  nullable=False),
        sa.Column("company_name",    sa.String(200),  nullable=False),
        sa.Column("official_url",    sa.String(2000), nullable=False),
        sa.Column("status",          sa.String(20),   nullable=False, server_default="pending"),
        sa.Column("evidence_level",  sa.String(50),   nullable=True),
        sa.Column("request_json",    sa.Text,         nullable=True),
        sa.Column("package_json",    sa.Text,         nullable=True),
        sa.Column("sources_json",    sa.Text,         nullable=True),
        sa.Column("validation_json", sa.Text,         nullable=True),
        sa.Column("meta_json",       sa.Text,         nullable=True),
        sa.Column("error_code",      sa.String(100),  nullable=True),
        sa.Column("error_message",   sa.Text,         nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_enrichment_jobs_company_id", "enrichment_jobs", ["company_id"])
    op.create_index("ix_enrichment_jobs_status",     "enrichment_jobs", ["status"])
    op.create_index("ix_enrichment_jobs_created_at", "enrichment_jobs", ["created_at"])
    op.create_index("ix_company_created",            "enrichment_jobs", ["company_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_company_created",            "enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_created_at", "enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_status",     "enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_company_id", "enrichment_jobs")
    op.drop_table("enrichment_jobs")
