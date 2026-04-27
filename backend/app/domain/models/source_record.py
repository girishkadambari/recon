"""
SourceRecord ORM model.
Table: source_records

One row per parsed row from an uploaded file.
raw_data_json stores the original row as-is (no transformation).
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.file_enums import SourceRecordStatus


class SourceRecord(
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
    TimestampMixin,
    UserAuditMixin,
    Base,
):
    __tablename__ = "source_records"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SourceRecordStatus.PARSED,
    )
    parse_error: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SourceRecord id={self.id} file={self.uploaded_file_id} row={self.row_number}>"