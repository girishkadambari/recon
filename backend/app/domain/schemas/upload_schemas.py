"""
Upload schemas — request/response Pydantic models for file upload endpoints.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UploadedFileResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    file_name: str
    file_category: str
    mime_type: str | None
    file_size_bytes: int | None
    status: str
    row_count: int | None
    parse_error: str | None
    created_at: datetime
    uploaded_by_user_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class UploadedFileListResponse(BaseModel):
    data: list[UploadedFileResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class SourceRecordResponse(BaseModel):
    id: uuid.UUID
    row_number: int
    raw_data_json: dict[str, Any]
    parse_status: str
    parse_error: str | None

    model_config = {"from_attributes": True}


class PreviewResponse(BaseModel):
    file_id: uuid.UUID
    file_name: str
    file_category: str
    column_names: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
