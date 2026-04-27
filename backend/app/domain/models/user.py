"""
User ORM model.
Table: users
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums.auth_enums import AuthProvider, UserStatus


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str ]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str ]] = mapped_column(String(2048), nullable=True)

    auth_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AuthProvider.GOOGLE,
    )
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserStatus.ACTIVE,
    )

    last_login_at: Mapped[Optional[datetime ]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("auth_provider", "provider_subject", name="uq_users_provider_subject"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"