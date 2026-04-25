"""
Canonical record models for each data source type.

All monetary amounts use NUMERIC(18,6) — never float.
All dates are timezone-aware.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from decimal import Decimal

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.core.constants import DEFAULT_CURRENCY


# ── PaymentRecord ─────────────────────────────────────────────────────────────
class PaymentRecord(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Normalized payment gateway transaction record.
    Covers: Stripe payments, Razorpay payments.
    """
    __tablename__ = "payment_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(nullable=False)

    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    settlement_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payout_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gateway: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    transaction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    settlement_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<PaymentRecord id={self.id} txn={self.transaction_id} amount={self.gross_amount}>"


# ── SettlementRecord ──────────────────────────────────────────────────────────
class SettlementRecord(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Normalized settlement / payout record.
    Covers: Razorpay settlements, Stripe payouts.
    """
    __tablename__ = "settlement_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(nullable=False)

    settlement_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payout_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    utr: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    gateway: Mapped[str | None] = mapped_column(String(100), nullable=True)

    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    settlement_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<SettlementRecord id={self.id} settlement={self.settlement_id} net={self.net_amount}>"


# ── BankRecord ────────────────────────────────────────────────────────────────
class BankRecord(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Normalized bank statement record.
    """
    __tablename__ = "bank_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(nullable=False)

    utr: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    credit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    debit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    transaction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<BankRecord id={self.id} utr={self.utr} credit={self.credit_amount}>"


# ── InvoiceRecord ─────────────────────────────────────────────────────────────
class InvoiceRecord(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Normalized invoice export record (internal ERP / custom invoicing).
    """
    __tablename__ = "invoice_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(nullable=False)

    invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    gateway: Mapped[str | None] = mapped_column(String(100), nullable=True)

    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    invoice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<InvoiceRecord id={self.id} invoice={self.invoice_id} amount={self.gross_amount}>"


# ── BillingTransactionRecord ──────────────────────────────────────────────────
class BillingTransactionRecord(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Normalized billing system transaction (Chargebee invoices/transactions).
    """
    __tablename__ = "billing_transaction_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(nullable=False)

    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gateway_txn_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    transaction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<BillingTransactionRecord id={self.id} txn={self.transaction_id} amount={self.gross_amount}>"
