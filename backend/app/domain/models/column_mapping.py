"""
ColumnMapping ORM model.
Table: column_mappings

Stores the confirmed mapping from raw column names → CanonicalField values
for a specific uploaded file. One row per uploaded file.
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import (
    Base,
    TimestampMixin,
    UserAuditMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.domain.enums.mapping_enums import MappingStatus


class ColumnMapping(
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
    TimestampMixin,
    UserAuditMixin,
    Base,
):
    __tablename__ = "column_mappings"

    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one mapping per file
        index=True,
    )

    # The actual mapping: {raw_column_name: canonical_field_or_ignore}
    # Example: {"payment_id": "transaction_id", "amount": "gross_amount", "notes": "ignore"}
    mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # AI suggestion (preserved separately so user can see what AI recommended)
    ai_suggested_mapping_json: Mapped[Optional[dict ]] = mapped_column(JSONB, nullable=True)
    ai_confidence_score: Mapped[Optional[int ]] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MappingStatus.PENDING_REVIEW,
        index=True,
    )

    confirmed_by_user_id: Mapped[Optional[uuid.UUID ]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    normalization_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )
    normalization_error: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ColumnMapping file={self.uploaded_file_id} status={self.status}>"