"""
AuditEvent ORM model.
Table: audit_events

Immutable — never updated, only inserted.
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    workspace_id: Mapped[Optional[uuid.UUID ]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID ]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[Optional[str ]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID ]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[Optional[dict ]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str ]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent type={self.event_type} actor={self.actor_user_id}>"