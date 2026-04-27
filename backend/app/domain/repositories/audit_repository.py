"""
Audit repository — insert-only. Never update audit records.
"""
from __future__ import annotations
from typing import Union, Optional
import uuid
from typing import Union, Any

from sqlalchemy.orm import Session

from app.domain.models.audit_event import AuditEvent
from app.domain.enums.audit_enums import AuditEventType


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        event_type: Union[AuditEventType, str],
        actor_user_id: Optional[uuid.UUID] = None,
        workspace_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        metadata:Optional[ dict[str, Any] ] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=str(event_type),
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        limit: int = 100,
    ) -> list[AuditEvent]:
        return (
            self.db.query(AuditEvent)
            .filter(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )