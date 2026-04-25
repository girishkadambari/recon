"""
ColumnMappingService — orchestrates AI suggestion + user confirmation.
"""
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ConflictError
from app.domain.enums.audit_enums import AuditEventType
from app.domain.enums.mapping_enums import MappingStatus
from app.domain.models.column_mapping import ColumnMapping
from app.domain.repositories.column_mapping_repository import ColumnMappingRepository
from app.domain.repositories.source_record_repository import SourceRecordRepository
from app.domain.repositories.uploaded_file_repository import UploadedFileRepository
from app.domain.services.audit_service import AuditService

logger = structlog.get_logger(__name__)


class ColumnMappingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.mapping_repo = ColumnMappingRepository(db)
        self.file_repo = UploadedFileRepository(db)
        self.source_repo = SourceRecordRepository(db)
        self.audit_svc = AuditService(db)

    def suggest_mapping(
        self,
        workspace_id: uuid.UUID,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ColumnMapping:
        """
        Ask Claude to suggest a column mapping.
        Saves the result as PENDING_REVIEW.
        Returns immediately — user must confirm before normalization.
        """
        # Validate file belongs to workspace
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"File {file_id} not found.")

        # Get sample rows  to send to the AI
        sample_records = self.source_repo.list_for_file(
            workspace_id=workspace_id,
            uploaded_file_id=file_id,
            limit=5,
        )
        sample_rows = [r.raw_data_json for r in sample_records]
        column_names = list(sample_rows[0].keys()) if sample_rows else []

        if not column_names:
            raise NotFoundError(
                f"File {file_id} has no parsed rows. "
                "Upload and parse the file before requesting a mapping."
            )

        # Call AI
        from app.ai.services.ai_column_mapping_service import suggest_column_mapping
        suggestion = suggest_column_mapping(
            file_category=uf.file_category,
            column_names=column_names,
            sample_rows=sample_rows,
        )

        # Persist
        mapping = self.mapping_repo.create_or_update(
            workspace_id=workspace_id,
            uploaded_file_id=file_id,
            mapping_json=suggestion["mapping"],
            ai_suggested_mapping_json=suggestion["mapping"],
            ai_confidence_score=suggestion.get("confidence_score"),
            created_by_user_id=user_id,
        )

        self.audit_svc.log(
            event_type=AuditEventType.COLUMN_MAPPING_SUGGESTED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="column_mapping",
            entity_id=mapping.id,
            metadata={
                "file_id": str(file_id),
                "confidence_score": suggestion.get("confidence_score"),
                "notes": suggestion.get("notes", ""),
            },
        )
        self.db.commit()

        logger.info(
            "Column mapping suggested",
            file_id=str(file_id),
            confidence=suggestion.get("confidence_score"),
        )
        return mapping

    def get_mapping(self, workspace_id: uuid.UUID, file_id: uuid.UUID) -> ColumnMapping:
        mapping = self.mapping_repo.get_by_file_id(file_id, workspace_id)
        if not mapping:
            raise NotFoundError(
                f"No column mapping found for file {file_id}. "
                "Call POST /api/column-mappings/{file_id}/suggest first."
            )
        return mapping

    def confirm_mapping(
        self,
        workspace_id: uuid.UUID,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
        updated_mapping: dict | None = None,
    ) -> ColumnMapping:
        """
        Confirm (possibly with edits) the AI-suggested mapping.
        This unlocks normalization.
        """
        mapping = self.get_mapping(workspace_id, file_id)

        if mapping.status == MappingStatus.CONFIRMED:
            raise ConflictError(
                f"Mapping for file {file_id} is already confirmed. "
                "Re-suggest to reset it."
            )

        mapping = self.mapping_repo.confirm(
            mapping,
            confirmed_by_user_id=user_id,
            updated_mapping=updated_mapping,
        )

        self.audit_svc.log(
            event_type=AuditEventType.COLUMN_MAPPING_CONFIRMED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="column_mapping",
            entity_id=mapping.id,
            metadata={"file_id": str(file_id)},
        )
        self.db.commit()
        return mapping
