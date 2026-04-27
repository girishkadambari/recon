"""
Reconciliation schemas — Pydantic v2 request/response models.
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class CreateRunRequest(BaseModel):
    name: str
    source_file_id: uuid.UUID
    target_file_id: uuid.UUID


class CreateRunRequestMulti(BaseModel):
    name: str
    uploaded_file_ids: list[uuid.UUID]


class ReconciliationRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    status: str
    run_date: Optional[datetime]
    completed_at: Optional[datetime]
    total_source_rows: int
    total_target_rows: int
    matched_count: int
    exception_count: int
    match_rate_pct: Optional[int]
    error_message: Optional[str]
    matched_amount: Decimal
    unmatched_amount: Decimal
    exception_summary:Optional[ dict[str, int] ] = None
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
    amount_delta: Optional[Decimal]
    date_delta_days: Optional[int]
    review_note: Optional[str]

    model_config = {"from_attributes": True}


class ReviewMatchRequest(BaseModel):
    action: str   # APPROVED or REJECTED
    note: Optional[str] = None


class ExceptionItemResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    record_id: uuid.UUID
    record_table: str
    file_role: str
    exception_type: str
    severity: str
    status: str
    amount: Optional[Decimal]
    currency: str
    details_json:Optional[ dict[str, Any] ]
    related_record_refs:Optional[ dict[str, Any] ] = None
    suggested_action: Optional[str] = None
    ai_explanation: Optional[str]
    resolution_note: Optional[str]

    model_config = {"from_attributes": True}


class ResolveExceptionRequest(BaseModel):
    status: str    # RESOLVED or WAIVED
    note: Optional[str] = None