"""
AuditService — thin wrapper over AuditRepository.
Provides a single log() method usable from any service.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domain.repositories.audit_repository import AuditRepository
from app.domain.enums.audit_enums import AuditEventType


class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditRepository(db)

    def log(
        self,
        event_type: AuditEventType | str,
        actor_user_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an audit event. Flush immediately but do not commit — the caller's transaction commits it."""
        self.repo.create(
            event_type=event_type,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
