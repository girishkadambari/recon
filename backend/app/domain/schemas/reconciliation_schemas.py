"""
Reconciliation schemas — Pydantic v2 request/response models.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class CreateRunRequest(BaseModel):
    name: str
    source_file_id: uuid.UUID
    target_file_id: uuid.UUID


class ReconciliationRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    status: str
    run_date: datetime | None
    completed_at: datetime | None
    total_source_rows: int
    total_target_rows: int
    matched_count: int
    exception_count: int
    match_rate_pct: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchCandidateResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source_record_id: uuid.UUID
    source_table: str
    target_record_id: uuid.UUID
    target_table: str
    confidence_score: int
    match_strategy: str
    status: str
    amount_delta: Decimal | None
    date_delta_days: int | None
    review_note: str | None

    model_config = {"from_attributes": True}


class ReviewMatchRequest(BaseModel):
    action: str   # APPROVED or REJECTED
    note: str | None = None


class ExceptionItemResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    record_id: uuid.UUID
    record_table: str
    file_role: str
    reason: str
    status: str
    amount: Decimal | None
    currency: str
    details_json: dict[str, Any] | None
    ai_explanation: str | None
    resolution_note: str | None

    model_config = {"from_attributes": True}


class ResolveExceptionRequest(BaseModel):
    status: str    # RESOLVED or WAIVED
    note: str | None = None
