"""
Audit repository — insert-only. Never update audit records.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domain.models.audit_event import AuditEvent
from app.domain.enums.audit_enums import AuditEventType


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        event_type: AuditEventType | str,
        actor_user_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
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
