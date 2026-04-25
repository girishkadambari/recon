"""
ReconciliationRun ORM model.
Table: reconciliation_runs

Groups multiple uploaded files into a single reconciliation job.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.reconciliation_enums import ReconciliationRunStatus


class ReconciliationRun(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    __tablename__ = "reconciliation_runs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ReconciliationRunStatus.PENDING,
        index=True,
    )
    run_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_source_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_target_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_rate_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ReconciliationRun id={self.id} name={self.name} status={self.status}>"
