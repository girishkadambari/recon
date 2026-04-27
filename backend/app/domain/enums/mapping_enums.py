"""
Column mapping and normalization enums.
"""
from enum import Enum


class CanonicalField(str, Enum):
    """
    Canonical field names used across all record types.
    These are the target field names that raw columns get mapped to.
    """
    # Identity
    TRANSACTION_ID = "transaction_id"
    PAYMENT_ID = "payment_id"
    ORDER_ID = "order_id"
    SETTLEMENT_ID = "settlement_id"
    PAYOUT_ID = "payout_id"
    INVOICE_ID = "invoice_id"
    SUBSCRIPTION_ID = "subscription_id"
    UTR = "utr"

    # Amounts (all Decimal)
    GROSS_AMOUNT = "gross_amount"
    NET_AMOUNT = "net_amount"
    FEE_AMOUNT = "fee_amount"
    TAX_AMOUNT = "tax_amount"
    REFUND_AMOUNT = "refund_amount"
    CREDIT_AMOUNT = "credit_amount"
    DEBIT_AMOUNT = "debit_amount"
    BALANCE = "balance"

    # Dates
    TRANSACTION_DATE = "transaction_date"
    SETTLEMENT_DATE = "settlement_date"
    INVOICE_DATE = "invoice_date"
    DUE_DATE = "due_date"

    # Identity / metadata
    CURRENCY = "currency"
    STATUS = "status"
    CUSTOMER_EMAIL = "customer_email"
    CUSTOMER_ID = "customer_id"
    DESCRIPTION = "description"
    NARRATION = "narration"
    REFERENCE = "reference"
    GATEWAY = "gateway"
    GATEWAY_TXN_ID = "gateway_txn_id"

    # Ignore
    IGNORE = "ignore"


class MappingStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class NormalizationStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
