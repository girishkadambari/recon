"""
Reconciliation routes.

POST /api/reconciliations                              — Create run
POST /api/reconciliations/{run_id}/execute             — Execute matching engine
GET  /api/reconciliations                              — List runs
GET  /api/reconciliations/{run_id}                     — Get run details
GET  /api/reconciliations/{run_id}/matches             — List matches
POST /api/reconciliations/{run_id}/matches/{id}/review — Approve/reject a match
GET  /api/reconciliations/{run_id}/exceptions          — List exceptions
POST /api/reconciliations/{run_id}/exceptions/{id}/resolve — Resolve/waive exception
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.dependencies import get_db
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.schemas.reconciliation_schemas import (
    CreateRunRequest,
    ExceptionItemResponse,
    MatchCandidateResponse,
    ReconciliationRunResponse,
    ResolveExceptionRequest,
    ReviewMatchRequest,
)
from app.domain.services.reconciliation_service import ReconciliationService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/reconciliations", tags=["reconciliations"])


@router.post("", summary="Create a new reconciliation run")
def create_run(
    payload: CreateRunRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Creates a run connecting SOURCE and TARGET files.
    Both files must already be normalized.
    Call /execute to actually run the matching engine.
    """
    svc = ReconciliationService(db)
    run = svc.create_run(
        workspace_id=ctx.active_workspace_id,
        user_id=ctx.user_id,
        name=payload.name,
        source_file_id=payload.source_file_id,
        target_file_id=payload.target_file_id,
    )
    return JSONResponse(
        status_code=201,
        content={"data": ReconciliationRunResponse.model_validate(run).model_dump(mode="json")},
    )


@router.post("/{run_id}/execute", summary="Execute the matching engine")
def execute_run(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Runs the deterministic matching engine.
    Produces MatchCandidates and ExceptionItems.
    Idempotent — raises 409 if already completed.
    """
    svc = ReconciliationService(db)
    run = svc.execute_run(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        user_id=ctx.user_id,
    )
    return JSONResponse(
        status_code=200,
        content={"data": ReconciliationRunResponse.model_validate(run).model_dump(mode="json")},
    )


@router.get("", summary="List reconciliation runs")
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    runs, total = svc.list_runs(
        workspace_id=ctx.active_workspace_id,
        page=page,
        page_size=page_size,
    )
    return JSONResponse(
        status_code=200,
        content={
            "data": [ReconciliationRunResponse.model_validate(r).model_dump(mode="json") for r in runs],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/{run_id}", summary="Get run details")
def get_run(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    run = svc.get_run(ctx.active_workspace_id, run_id)
    return JSONResponse(
        status_code=200,
        content={"data": ReconciliationRunResponse.model_validate(run).model_dump(mode="json")},
    )


@router.get("/{run_id}/matches", summary="List match candidates")
def list_matches(
    run_id: uuid.UUID,
    status: str | None = Query(None),
    min_confidence: int | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = ReconciliationRepository(db)
    offset = (page - 1) * page_size
    matches, total = repo.list_matches(
        run_id=run_id,
        workspace_id=ctx.active_workspace_id,
        status=status,
        min_confidence=min_confidence,
        limit=page_size,
        offset=offset,
    )
    return JSONResponse(
        status_code=200,
        content={
            "data": [MatchCandidateResponse.model_validate(m).model_dump(mode="json") for m in matches],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.post("/{run_id}/matches/{match_id}/review", summary="Approve or reject a match")
def review_match(
    run_id: uuid.UUID,
    match_id: uuid.UUID,
    payload: ReviewMatchRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    match = svc.review_match(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        match_id=match_id,
        action=payload.action,
        user_id=ctx.user_id,
        note=payload.note,
    )
    return JSONResponse(
        status_code=200,
        content={"data": MatchCandidateResponse.model_validate(match).model_dump(mode="json")},
    )


@router.get("/{run_id}/exceptions", summary="List exceptions")
def list_exceptions(
    run_id: uuid.UUID,
    status: str | None = Query(None),
    reason: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = ReconciliationRepository(db)
    offset = (page - 1) * page_size
    exceptions, total = repo.list_exceptions(
        run_id=run_id,
        workspace_id=ctx.active_workspace_id,
        status=status,
        reason=reason,
        limit=page_size,
        offset=offset,
    )
    return JSONResponse(
        status_code=200,
        content={
            "data": [ExceptionItemResponse.model_validate(e).model_dump(mode="json") for e in exceptions],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.post("/{run_id}/exceptions/{exception_id}/resolve", summary="Resolve or waive an exception")
def resolve_exception(
    run_id: uuid.UUID,
    exception_id: uuid.UUID,
    payload: ResolveExceptionRequest,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    exc = svc.resolve_exception(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        exception_id=exception_id,
        status=payload.status,
        user_id=ctx.user_id,
        note=payload.note,
    )
    return JSONResponse(
        status_code=200,
        content={"data": ExceptionItemResponse.model_validate(exc).model_dump(mode="json")},
    )
