"""
Reconciliation run and match candidate enums.
"""
from enum import Enum


class ReconciliationRunStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileRole(str, Enum):
    """Role of a file within a reconciliation run."""
    SOURCE = "SOURCE"   # gateway / billing file (e.g. Stripe payments)
    TARGET = "TARGET"   # bank statement / settlement file to reconcile against
    BILLING = "BILLING"
    PAYMENT = "PAYMENT"
    SETTLEMENT = "SETTLEMENT"
    BANK = "BANK"


class MatchStrategy(str, Enum):
    """Which algorithm produced the match."""
    EXACT_ID = "EXACT_ID"             # transaction_id / mapping match — confidence 100
    UTR = "UTR"                       # Bank UTR ↔ Settlement Payout ID match — confidence 98
    AMOUNT_DATE = "AMOUNT_DATE"       # exact amount + date within window — confidence 92
    NET_SETTLEMENT = "NET_SETTLEMENT" # gross-fee-tax balance matching — confidence 88
    SETTLEMENT_BATCH = "SETTLEMENT_BATCH" # Grouped payment matching to settlement batch — confidence 90
    AMOUNT_ONLY = "AMOUNT_ONLY"       # exact amount, no reliable date — confidence 75
    FUZZY_REF = "FUZZY_REF"           # substring reference match — confidence 65
    FUZZY_AMOUNT = "FUZZY_AMOUNT"     # amount within tolerance — confidence 60


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"               # auto-confirmed at high confidence
    PENDING_REVIEW = "PENDING_REVIEW" # medium confidence — needs human review
    APPROVED = "APPROVED"             # human approved
    REJECTED = "REJECTED"             # human rejected


class ExceptionReason(str, Enum):
    UNMATCHED_SOURCE = "UNMATCHED_SOURCE"   # row in SOURCE has no match in TARGET
    UNMATCHED_TARGET = "UNMATCHED_TARGET"   # row in TARGET has no match in SOURCE
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"     # matched by ID but amounts differ
    DATE_MISMATCH = "DATE_MISMATCH"         # matched by ID/amount but dates too far apart
    DUPLICATE_MATCH = "DUPLICATE_MATCH"     # multiple records compete for same match


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
