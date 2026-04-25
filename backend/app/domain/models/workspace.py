"""
Workspace ORM model.
Table: workspaces
"""
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UserAuditMixin
from app.domain.enums.auth_enums import WorkspaceStatus


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, UserAuditMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WorkspaceStatus.ACTIVE,
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} name={self.name}>"
