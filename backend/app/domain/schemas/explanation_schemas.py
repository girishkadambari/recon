"""
Phase 5 schemas — AI explanation and run summary response models.
"""
from typing import Any

import uuid
from pydantic import BaseModel


class ExceptionExplanationResponse(BaseModel):
    exception_id: str
    explanation: str | None = None
    probable_cause: str | None = None
    recommended_action: str | None = None
    confidence: str | None = None
    ai_explanation: str | None = None   # cached full text
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
    match_rate_pct: int | None
    headline: str
    summary: str
    risk_level: str
    key_findings: list[str]
    recommended_actions: list[str]
    requires_immediate_attention: bool
