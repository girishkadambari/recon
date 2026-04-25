"""
Alembic migration: 0004 — Create reconciliation tables.

Tables created:
  - reconciliation_runs
  - reconciliation_run_files
  - match_candidates
  - exception_items
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(18, 6)


def _audit_cols():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    ]


def upgrade() -> None:
    # ── reconciliation_runs ──────────────────────────────────────────
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("run_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_source_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_target_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("exception_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("match_rate_pct", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_reconciliation_runs_workspace_id", "reconciliation_runs", ["workspace_id"])
    op.create_index("ix_reconciliation_runs_status", "reconciliation_runs", ["status"])

    # ── reconciliation_run_files ─────────────────────────────────────
    op.create_table(
        "reconciliation_run_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_role", sa.String(20), nullable=False),
        *_audit_cols(),
    )
    op.create_index("ix_reconciliation_run_files_run_id", "reconciliation_run_files", ["run_id"])
    op.create_index("ix_reconciliation_run_files_uploaded_file_id", "reconciliation_run_files", ["uploaded_file_id"])

    # ── match_candidates ─────────────────────────────────────────────
    op.create_table(
        "match_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_table", sa.String(100), nullable=False),
        sa.Column("target_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_table", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Integer, nullable=False),
        sa.Column("match_strategy", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="MATCHED"),
        sa.Column("amount_delta", MONEY, nullable=True),
        sa.Column("date_delta_days", sa.Integer, nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_match_candidates_run_id", "match_candidates", ["run_id"])
    op.create_index("ix_match_candidates_workspace_id", "match_candidates", ["workspace_id"])
    op.create_index("ix_match_candidates_confidence_score", "match_candidates", ["confidence_score"])
    op.create_index("ix_match_candidates_status", "match_candidates", ["status"])
    op.create_index("ix_match_candidates_source_record_id", "match_candidates", ["source_record_id"])
    op.create_index("ix_match_candidates_target_record_id", "match_candidates", ["target_record_id"])

    # ── exception_items ──────────────────────────────────────────────
    op.create_table(
        "exception_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_table", sa.String(100), nullable=False),
        sa.Column("file_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="OPEN"),
        sa.Column("amount", MONEY, nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("details_json", postgresql.JSONB, nullable=True),
        sa.Column("ai_explanation", sa.Text, nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_exception_items_run_id", "exception_items", ["run_id"])
    op.create_index("ix_exception_items_workspace_id", "exception_items", ["workspace_id"])
    op.create_index("ix_exception_items_status", "exception_items", ["status"])
    op.create_index("ix_exception_items_reason", "exception_items", ["reason"])
    op.create_index("ix_exception_items_record_id", "exception_items", ["record_id"])


def downgrade() -> None:
    for t in ["exception_items", "match_candidates", "reconciliation_run_files", "reconciliation_runs"]:
        op.drop_table(t)
