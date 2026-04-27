"""
ColumnMapping repository.
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.domain.models.column_mapping import ColumnMapping
from app.domain.enums.mapping_enums import MappingStatus, NormalizationStatus


class ColumnMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_file_id(
        self, uploaded_file_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ColumnMapping]:
        return (
            self.db.query(ColumnMapping)
            .filter(
                ColumnMapping.uploaded_file_id == uploaded_file_id,
                ColumnMapping.workspace_id == workspace_id,
            )
            .first()
        )

    def create_or_update(
        self,
        workspace_id: uuid.UUID,
        uploaded_file_id: uuid.UUID,
        mapping_json: dict,
        ai_suggested_mapping_json: Optional[dict],
        ai_confidence_score: Optional[int],
        created_by_user_id: uuid.UUID,
    ) -> ColumnMapping:
        existing = self.get_by_file_id(uploaded_file_id, workspace_id)
        if existing:
            existing.mapping_json = mapping_json
            existing.ai_suggested_mapping_json = ai_suggested_mapping_json
            existing.ai_confidence_score = ai_confidence_score
            existing.status = MappingStatus.PENDING_REVIEW
            existing.normalization_status = NormalizationStatus.PENDING
            existing.normalization_error = None
            from app.core.dates import utcnow
            existing.updated_at = utcnow()
            existing.updated_by_user_id = created_by_user_id
            self.db.flush()
            return existing

        mapping = ColumnMapping(
            workspace_id=workspace_id,
            uploaded_file_id=uploaded_file_id,
            mapping_json=mapping_json,
            ai_suggested_mapping_json=ai_suggested_mapping_json,
            ai_confidence_score=ai_confidence_score,
            status=MappingStatus.PENDING_REVIEW,
            normalization_status=NormalizationStatus.PENDING,
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(mapping)
        self.db.flush()
        return mapping

    def confirm(
        self,
        column_mapping: ColumnMapping,
        confirmed_by_user_id: uuid.UUID,
        updated_mapping: Optional[dict] = None,
    ) -> ColumnMapping:
        from app.core.dates import utcnow
        if updated_mapping is not None:
            column_mapping.mapping_json = updated_mapping
        column_mapping.status = MappingStatus.CONFIRMED
        column_mapping.confirmed_by_user_id = confirmed_by_user_id
        column_mapping.updated_at = utcnow()
        column_mapping.updated_by_user_id = confirmed_by_user_id
        self.db.flush()
        return column_mapping

    def update_normalization_status(
        self,
        column_mapping: ColumnMapping,
        status: str,
        error: Optional[str] = None,
    ) -> ColumnMapping:
        from app.core.dates import utcnow
        column_mapping.normalization_status = status
        column_mapping.normalization_error = error
        column_mapping.updated_at = utcnow()
        self.db.flush()
        return column_mapping