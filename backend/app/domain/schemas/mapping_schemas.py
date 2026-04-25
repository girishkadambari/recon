"""
Phase 3 schemas — column mapping and normalization API request/response models.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ColumnMappingResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    mapping_json: dict[str, str]
    ai_suggested_mapping_json: dict[str, str] | None
    ai_confidence_score: int | None
    status: str
    normalization_status: str
    normalization_error: str | None
    confirmed_by_user_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfirmMappingRequest(BaseModel):
    """
    Optional updated mapping the user can send when confirming.
    If not provided, the AI-suggested mapping is used as-is.
    """
    mapping: dict[str, str] | None = None


class NormalizationResponse(BaseModel):
    canonical_table: str
    rows_inserted: int
    normalization_status: str


class CanonicalRowsResponse(BaseModel):
    file_id: uuid.UUID
    canonical_table: str
    rows: list[dict[str, Any]]
    count: int
