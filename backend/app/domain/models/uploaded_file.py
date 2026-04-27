"""
UploadedFile ORM model.
Table: uploaded_files
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.file_enums import FileCategory, UploadedFileStatus


class UploadedFile(
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
    TimestampMixin,
    UserAuditMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "uploaded_files"

    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str ]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int ]] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[Optional[str ]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UploadedFileStatus.UPLOADED,
        index=True,
    )
    row_count: Mapped[Optional[int ]] = mapped_column(Integer, nullable=True)
    parse_error: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)
    uploaded_by_user_id: Mapped[Optional[uuid.UUID ]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<UploadedFile id={self.id} name={self.file_name} status={self.status}>"