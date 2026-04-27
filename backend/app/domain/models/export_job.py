"""
ExportJob ORM model.
Table: export_jobs

Tracks the generation lifecycle of a reconciliation XLSX export.
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.export_enums import ExportFormat, ExportScope, ExportStatus


class ExportJob(
    UUIDPrimaryKeyMixin, WorkspaceScopedMixin, TimestampMixin, UserAuditMixin, Base
):
    __tablename__ = "export_jobs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ExportStatus.PENDING,
        index=True,
    )
    export_format: Mapped[str] = mapped_column(String(20), nullable=False, default=ExportFormat.XLSX)
    export_scope: Mapped[str] = mapped_column(String(50), nullable=False, default=ExportScope.FULL)

    # S3 storage key where the generated file lives
    storage_key: Mapped[Optional[str ]] = mapped_column(String(1024), nullable=True)

    # Display metadata
    file_name: Mapped[Optional[str ]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[Optional[int ]] = mapped_column(Integer, nullable=True)

    # Row counts written
    matched_rows_exported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exception_rows_exported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ExportJob id={self.id} run={self.run_id} status={self.status}>"