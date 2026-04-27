"""
Phase 5 schemas — AI explanation and run summary response models.
"""
from __future__ import annotations
from typing import Optional
from typing import Any

import uuid
from pydantic import BaseModel


class ExceptionExplanationResponse(BaseModel):
    exception_id: str
    explanation: Optional[str] = None
    probable_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    confidence: Optional[str] = None
    ai_explanation: Optional[str] = None   # cached full text
    cached: bool = False


class BatchExplainResponse(BaseModel):
    run_id: str
    explained: int
    skipped: int
    failed: int = 0
    capped_at: int = 50


class RunSummaryResponse(BaseModel):
    run_id: str
    run_name: str
    match_rate_pct: Optional[int]
    headline: str
    summary: str
    risk_level: str
    key_findings: list[str]
    recommended_actions: list[str]
    requires_immediate_attention: bool