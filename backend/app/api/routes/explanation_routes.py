"""
Phase 5 — AI explanation routes (added to reconciliation namespace).

POST /api/reconciliations/{run_id}/exceptions/{exception_id}/explain
    → Generate or fetch AI explanation for a single exception

POST /api/reconciliations/{run_id}/explain-all
    → Batch explain all OPEN exceptions (capped at 50)

GET  /api/reconciliations/{run_id}/summary
    → AI executive summary for the entire run
"""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.dependencies import get_db
from app.domain.services.exception_explanation_service import ExceptionExplanationService

logger = structlog.get_logger(__name__)

# This router is mounted under /api/reconciliations in the main router
router = APIRouter(prefix="/api/reconciliations", tags=["explanations"])


@router.post(
    "/{run_id}/exceptions/{exception_id}/explain",
    summary="Generate AI explanation for a single exception",
)
def explain_exception(
    run_id: uuid.UUID,
    exception_id: uuid.UUID,
    force_refresh: bool = Query(False, description="Force Claude to re-generate even if explanation already exists"),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Calls Claude to explain why this record could not be matched.
    Returns the explanation along with probable cause and recommended action.
    AI is advisory only — this never changes the exception status.
    Explanations are cached in the DB; use force_refresh=true to regenerate.
    """
    svc = ExceptionExplanationService(db)
    result = svc.explain_one(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        exception_id=exception_id,
        user_id=ctx.user_id,
        force_refresh=force_refresh,
    )
    return JSONResponse(status_code=200, content={"data": result})


@router.post(
    "/{run_id}/explain-all",
    summary="Batch-generate AI explanations for all open exceptions",
)
def explain_all_exceptions(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Generates AI explanations for all OPEN exceptions in the run.
    Skips exceptions that already have explanations.
    Capped at 50 exceptions per call to control API cost.
    """
    svc = ExceptionExplanationService(db)
    result = svc.explain_all_open(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        user_id=ctx.user_id,
    )
    return JSONResponse(status_code=200, content={"data": result})


@router.get(
    "/{run_id}/summary",
    summary="Generate AI executive summary for a completed run",
)
def get_run_summary(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Generates a business-friendly AI summary of the reconciliation run.
    Includes match rate analysis, key findings, risk level, and recommended actions.
    Generated fresh on each call — not cached.
    """
    svc = ExceptionExplanationService(db)
    result = svc.generate_run_summary(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
    )
    return JSONResponse(status_code=200, content={"data": result})
