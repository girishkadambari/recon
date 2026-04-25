"""
Reconciliation run and match candidate enums.
"""
from enum import StrEnum


class ReconciliationRunStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileRole(StrEnum):
    """Role of a file within a reconciliation run."""
    SOURCE = "SOURCE"   # gateway / billing file (e.g. Stripe payments)
    TARGET = "TARGET"   # bank statement / settlement file to reconcile against


class MatchStrategy(StrEnum):
    """Which algorithm produced the match."""
    EXACT_ID = "EXACT_ID"             # transaction_id or UTR exact match — confidence 100
    AMOUNT_DATE = "AMOUNT_DATE"       # exact amount + date within window — confidence 90
    AMOUNT_ONLY = "AMOUNT_ONLY"       # exact amount, no reliable date — confidence 75
    FUZZY_AMOUNT = "FUZZY_AMOUNT"     # amount within tolerance — confidence 60


class MatchStatus(StrEnum):
    MATCHED = "MATCHED"               # auto-confirmed at high confidence
    PENDING_REVIEW = "PENDING_REVIEW" # medium confidence — needs human review
    APPROVED = "APPROVED"             # human approved
    REJECTED = "REJECTED"             # human rejected


class ExceptionReason(StrEnum):
    UNMATCHED_SOURCE = "UNMATCHED_SOURCE"   # row in SOURCE has no match in TARGET
    UNMATCHED_TARGET = "UNMATCHED_TARGET"   # row in TARGET has no match in SOURCE
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"     # matched by ID but amounts differ
    DATE_MISMATCH = "DATE_MISMATCH"         # matched by ID/amount but dates too far apart
    DUPLICATE_MATCH = "DUPLICATE_MATCH"     # multiple records compete for same match


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
