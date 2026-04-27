"""
v0.2 upgrades: multi-file support, billing fields, and expanded exceptions.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update reconciliation_runs
    op.add_column("reconciliation_runs", sa.Column("matched_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"))
    op.add_column("reconciliation_runs", sa.Column("unmatched_amount", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"))

    # 2. Add billing_transaction_records fields
    op.add_column("billing_transaction_records", sa.Column("billing_system", sa.String(length=100), nullable=True))
    op.add_column("billing_transaction_records", sa.Column("billing_transaction_id", sa.String(length=255), nullable=True))
    op.add_column("billing_transaction_records", sa.Column("billing_invoice_id", sa.String(length=255), nullable=True))
    op.add_column("billing_transaction_records", sa.Column("billing_customer_id", sa.String(length=255), nullable=True))
    op.add_column("billing_transaction_records", sa.Column("billing_subscription_id", sa.String(length=255), nullable=True))
    op.add_column("billing_transaction_records", sa.Column("gateway_transaction_id", sa.String(length=255), nullable=True))
    
    op.create_index(op.f("ix_billing_transaction_records_billing_transaction_id"), "billing_transaction_records", ["billing_transaction_id"], unique=False)
    op.create_index(op.f("ix_billing_transaction_records_billing_invoice_id"), "billing_transaction_records", ["billing_invoice_id"], unique=False)
    op.create_index(op.f("ix_billing_transaction_records_gateway_transaction_id"), "billing_transaction_records", ["gateway_transaction_id"], unique=False)

    # 3. Update exception_items
    op.add_column("exception_items", sa.Column("exception_type", sa.String(length=100), nullable=True))
    op.add_column("exception_items", sa.Column("severity", sa.String(length=20), nullable=False, server_default="MEDIUM"))
    op.add_column("exception_items", sa.Column("related_record_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("exception_items", sa.Column("suggested_action", sa.String(length=255), nullable=True))
    
    # Copy data from reason to exception_type before dropping reason
    op.execute("UPDATE exception_items SET exception_type = reason")
    op.alter_column("exception_items", "exception_type", nullable=False)
    op.drop_column("exception_items", "reason")
    
    op.create_index(op.f("ix_exception_items_exception_type"), "exception_items", ["exception_type"], unique=False)
    op.create_index(op.f("ix_exception_items_severity"), "exception_items", ["severity"], unique=False)

    # 4. table reconciliation_run_files already exists (from 0004)
    # No changes needed here for now.
    pass


def downgrade() -> None:
    op.drop_table("reconciliation_run_files")
    
    op.add_column("exception_items", sa.Column("reason", sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.execute("UPDATE exception_items SET reason = exception_type")
    op.alter_column("exception_items", "reason", nullable=False)
    
    op.drop_column("exception_items", "suggested_action")
    op.drop_column("exception_items", "related_record_refs")
    op.drop_column("exception_items", "severity")
    op.drop_column("exception_items", "exception_type")
    
    op.drop_column("billing_transaction_records", "gateway_transaction_id")
    op.drop_column("billing_transaction_records", "billing_subscription_id")
    op.drop_column("billing_transaction_records", "billing_customer_id")
    op.drop_column("billing_transaction_records", "billing_invoice_id")
    op.drop_column("billing_transaction_records", "billing_transaction_id")
    op.drop_column("billing_transaction_records", "billing_system")
    
    op.drop_column("reconciliation_runs", "unmatched_amount")
    op.drop_column("reconciliation_runs", "matched_amount")
