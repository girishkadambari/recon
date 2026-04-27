"""
UserSession ORM model.
Table: user_sessions
Optional — used for refresh token tracking.
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime ]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime ]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[Optional[str ]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str ]] = mapped_column(Text, nullable=True)

    @property
    def is_active(self) -> bool:
        from app.core.dates import utcnow
        now = utcnow()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < now:
            return False
        return True

    def __repr__(self) -> str:
        return f"<UserSession id={self.id} user={self.user_id}>"