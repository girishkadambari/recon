"""
AuditService — thin wrapper over AuditRepository.
Provides a single log() method usable from any service.
"""
from __future__ import annotations
from typing import Union, Optional
import uuid
from typing import Union, Any

from sqlalchemy.orm import Session

from app.domain.repositories.audit_repository import AuditRepository
from app.domain.enums.audit_enums import AuditEventType


class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditRepository(db)

    def log(
        self,
        event_type: Union[AuditEventType, str],
        actor_user_id: Optional[uuid.UUID] = None,
        workspace_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        metadata:Optional[ dict[str, Any] ] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
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

    def list_activity(self, workspace_id: uuid.UUID, limit: int = 50):
        return self.repo.list_for_workspace(workspace_id, limit=limit)