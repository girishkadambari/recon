"""
Alembic migration: 0003 — Create column mapping + canonical record tables.

Tables created:
  - column_mappings
  - payment_records
  - settlement_records
  - bank_records
  - invoice_records
  - billing_transaction_records
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(18, 6)
WS_FK = sa.ForeignKey("workspaces.id", ondelete="CASCADE")
USER_FK = lambda col: sa.ForeignKey("users.id", ondelete="SET NULL")  # noqa: E731


def _audit_cols():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    ]


def upgrade() -> None:
    # ── column_mappings ──────────────────────────────────────────────
    op.create_table(
        "column_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("mapping_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ai_suggested_mapping_json", postgresql.JSONB, nullable=True),
        sa.Column("ai_confidence_score", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("normalization_status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("normalization_error", sa.Text, nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_column_mappings_workspace_id", "column_mappings", ["workspace_id"])
    op.create_index("ix_column_mappings_uploaded_file_id", "column_mappings", ["uploaded_file_id"])
    op.create_index("ix_column_mappings_status", "column_mappings", ["status"])

    # ── Helper: create a canonical record table ──────────────────────
    def _canonical_table(name: str, extra_cols: list) -> None:
        op.create_table(
            name,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False),
            sa.Column("row_number", sa.Integer, nullable=False),
            *extra_cols,
            sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
            *_audit_cols(),
        )
        op.create_index(f"ix_{name}_workspace_id", name, ["workspace_id"])
        op.create_index(f"ix_{name}_uploaded_file_id", name, ["uploaded_file_id"])

    # ── payment_records ──────────────────────────────────────────────
    _canonical_table("payment_records", [
        sa.Column("transaction_id", sa.String(255), nullable=True),
        sa.Column("payment_id", sa.String(255), nullable=True),
        sa.Column("order_id", sa.String(255), nullable=True),
        sa.Column("settlement_id", sa.String(255), nullable=True),
        sa.Column("payout_id", sa.String(255), nullable=True),
        sa.Column("invoice_id", sa.String(255), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_id", sa.String(255), nullable=True),
        sa.Column("gross_amount", MONEY, nullable=True),
        sa.Column("fee_amount", MONEY, nullable=True),
        sa.Column("tax_amount", MONEY, nullable=True),
        sa.Column("refund_amount", MONEY, nullable=True),
        sa.Column("net_amount", MONEY, nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("gateway", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settlement_date", sa.DateTime(timezone=True), nullable=True),
    ])
    op.create_index("ix_payment_records_transaction_id", "payment_records", ["transaction_id"])
    op.create_index("ix_payment_records_settlement_id", "payment_records", ["settlement_id"])
    op.create_index("ix_payment_records_transaction_date", "payment_records", ["transaction_date"])

    # ── settlement_records ───────────────────────────────────────────
    _canonical_table("settlement_records", [
        sa.Column("settlement_id", sa.String(255), nullable=True),
        sa.Column("payout_id", sa.String(255), nullable=True),
        sa.Column("utr", sa.String(255), nullable=True),
        sa.Column("gateway", sa.String(100), nullable=True),
        sa.Column("gross_amount", MONEY, nullable=True),
        sa.Column("fee_amount", MONEY, nullable=True),
        sa.Column("tax_amount", MONEY, nullable=True),
        sa.Column("refund_amount", MONEY, nullable=True),
        sa.Column("net_amount", MONEY, nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("settlement_date", sa.DateTime(timezone=True), nullable=True),
    ])
    op.create_index("ix_settlement_records_settlement_id", "settlement_records", ["settlement_id"])
    op.create_index("ix_settlement_records_utr", "settlement_records", ["utr"])
    op.create_index("ix_settlement_records_settlement_date", "settlement_records", ["settlement_date"])

    # ── bank_records ─────────────────────────────────────────────────
    _canonical_table("bank_records", [
        sa.Column("utr", sa.String(255), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("narration", sa.Text, nullable=True),
        sa.Column("credit_amount", MONEY, nullable=True),
        sa.Column("debit_amount", MONEY, nullable=True),
        sa.Column("balance", MONEY, nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
    ])
    op.create_index("ix_bank_records_utr", "bank_records", ["utr"])
    op.create_index("ix_bank_records_transaction_date", "bank_records", ["transaction_date"])

    # ── invoice_records ──────────────────────────────────────────────
    _canonical_table("invoice_records", [
        sa.Column("invoice_id", sa.String(255), nullable=True),
        sa.Column("customer_id", sa.String(255), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("subscription_id", sa.String(255), nullable=True),
        sa.Column("payment_id", sa.String(255), nullable=True),
        sa.Column("gateway", sa.String(100), nullable=True),
        sa.Column("gross_amount", MONEY, nullable=True),
        sa.Column("net_amount", MONEY, nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
    ])
    op.create_index("ix_invoice_records_invoice_id", "invoice_records", ["invoice_id"])
    op.create_index("ix_invoice_records_payment_id", "invoice_records", ["payment_id"])
    op.create_index("ix_invoice_records_invoice_date", "invoice_records", ["invoice_date"])

    # ── billing_transaction_records ──────────────────────────────────
    _canonical_table("billing_transaction_records", [
        sa.Column("transaction_id", sa.String(255), nullable=True),
        sa.Column("invoice_id", sa.String(255), nullable=True),
        sa.Column("subscription_id", sa.String(255), nullable=True),
        sa.Column("customer_id", sa.String(255), nullable=True),
        sa.Column("gateway", sa.String(100), nullable=True),
        sa.Column("gateway_txn_id", sa.String(255), nullable=True),
        sa.Column("gross_amount", MONEY, nullable=True),
        sa.Column("net_amount", MONEY, nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
    ])
    op.create_index("ix_billing_transaction_records_transaction_id", "billing_transaction_records", ["transaction_id"])
    op.create_index("ix_billing_transaction_records_gateway_txn_id", "billing_transaction_records", ["gateway_txn_id"])


def downgrade() -> None:
    for t in [
        "billing_transaction_records",
        "invoice_records",
        "bank_records",
        "settlement_records",
        "payment_records",
        "column_mappings",
    ]:
        op.drop_table(t)
