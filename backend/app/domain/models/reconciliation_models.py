"""
ReconciliationRunFile, MatchCandidate, ExceptionItem ORM models.
"""
from __future__ import annotations
from typing import Optional
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.exception_enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionStatus,
)
from app.domain.enums.reconciliation_enums import (
    FileRole,
    MatchStatus,
    MatchStrategy,
)


# ── ReconciliationRunFile ─────────────────────────────────────────────────────
class ReconciliationRunFile(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    Associates an uploaded file with a reconciliation run.
    One run has exactly two files: SOURCE and TARGET.
    """
    __tablename__ = "reconciliation_run_files"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_role: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:
        return f"<ReconciliationRunFile run={self.run_id} file={self.uploaded_file_id} role={self.file_role}>"


# ── MatchCandidate ────────────────────────────────────────────────────────────
class MatchCandidate(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    A potential match between a source canonical record and a target canonical record.
    """
    __tablename__ = "match_candidates"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source record (payment / billing side)
    source_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)

    # Target record (bank / settlement side)
    target_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)

    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    match_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MatchStatus.MATCHED,
        index=True,
    )

    # Deltas for human review
    amount_delta: Mapped[Optional[Decimal ]] = mapped_column(Numeric(18, 6), nullable=True)
    date_delta_days: Mapped[Optional[int ]] = mapped_column(Integer, nullable=True)

    # Human review
    reviewed_by_user_id: Mapped[Optional[uuid.UUID ]] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_note: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<MatchCandidate id={self.id} "
            f"score={self.confidence_score} strategy={self.match_strategy} status={self.status}>"
        )


# ── ExceptionItem ─────────────────────────────────────────────────────────────
class ExceptionItem(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    """
    An unmatched or disputed record from a reconciliation run.
    AI explanation (Phase 5) is stored in ai_explanation.
    """
    __tablename__ = "exception_items"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which record is the exception
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    record_table: Mapped[str] = mapped_column(String(100), nullable=False)
    file_role: Mapped[str] = mapped_column(String(20), nullable=False)  # SOURCE or TARGET

    exception_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExceptionSeverity.MEDIUM, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ExceptionStatus.OPEN,
        index=True,
    )
    
    # Stores {payment_id: "...", settlement_id: "..."} for multi-way lookup
    related_record_refs: Mapped[Optional[dict ]] = mapped_column(JSONB, nullable=True)
    
    # Actionable 1-liner for the user
    suggested_action: Mapped[Optional[str ]] = mapped_column(String(255), nullable=True)

    # Amount context for display
    amount: Mapped[Optional[Decimal ]] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    # Raw details for AI explanation context
    details_json: Mapped[Optional[dict ]] = mapped_column(JSONB, nullable=True)

    # AI-generated explanation (filled in Phase 5)
    ai_explanation: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    # Human resolution
    resolved_by_user_id: Mapped[Optional[uuid.UUID ]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolution_note: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ExceptionItem id={self.id} type={self.exception_type} status={self.status}>"