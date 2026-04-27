"""
Reconciliation Runs (v0.2 plural endpoints).
Supports multi-file reconciliation.
"""
from __future__ import annotations
from typing import Optional
import uuid
from fastapi import Request, APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.dependencies import get_db
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.schemas.reconciliation_schemas import (
    CreateRunRequestMulti,
    ExceptionItemResponse,
    MatchCandidateResponse,
    ReconciliationRunResponse,
    ResolveExceptionRequest,
    ReviewMatchRequest,
)
from app.domain.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/api/reconciliation-runs", tags=["reconciliations-v2"])


@router.post("", summary="Create a new multi-file reconciliation run")
def create_run(
    payload: CreateRunRequestMulti,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    run = svc.create_run_multi(
        workspace_id=ctx.active_workspace_id,
        user_id=ctx.user_id,
        name=payload.name,
        uploaded_file_ids=payload.uploaded_file_ids,
    )
    return JSONResponse(
        status_code=201,
        content={"data": ReconciliationRunResponse.model_validate(run).model_dump(mode="json")},
    )


@router.post("/{run_id}/run", summary="Execute the multi-file reconciliation")
def execute_run(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
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
    request: Request,
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
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": [ReconciliationRunResponse.model_validate(r).model_dump(mode="json") for r in runs],
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            "request_id": request_id,
        },
    )


# ── Global Exceptions ──────────────────────────────────────────────

@router.get("/global/exceptions", summary="List all exceptions in workspace", tags=["exceptions"])
def list_global_exceptions(
    request: Request,
    status: Optional[str] = Query(None),
    exception_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = ReconciliationRepository(db)
    offset = (page - 1) * page_size
    exceptions, total = repo.list_exceptions(
        workspace_id=ctx.active_workspace_id,
        status=status,
        exception_type=exception_type,
        severity=severity,
        limit=page_size,
        offset=offset,
    )
    request_id = getattr(request.state, "request_id", None)
    
    # Calculate summary stats for the dashboard cards
    from sqlalchemy import func
    from app.domain.models.reconciliation_models import ExceptionItem
    from app.domain.enums.reconciliation_enums import ExceptionStatus
    
    open_count = db.query(func.count(ExceptionItem.id)).filter(
        ExceptionItem.workspace_id == ctx.active_workspace_id,
        ExceptionItem.status == ExceptionStatus.OPEN
    ).scalar() or 0
    
    critical_count = db.query(func.count(ExceptionItem.id)).filter(
        ExceptionItem.workspace_id == ctx.active_workspace_id,
        ExceptionItem.severity == "CRITICAL"
    ).scalar() or 0
    
    total_exposure = db.query(func.sum(ExceptionItem.amount)).filter(
        ExceptionItem.workspace_id == ctx.active_workspace_id
    ).scalar() or 0
    
    return JSONResponse(
        status_code=200,
        content={
            "data": [ExceptionItemResponse.model_validate(e).model_dump(mode="json") for e in exceptions],
            "stats": {
                "open": open_count,
                "critical": critical_count,
                "exposure": float(total_exposure),
                "auto_resolvable": 14, # Placeholder for logic
            },
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            "request_id": request_id,
        },
    )


@router.get("/{run_id}", summary="Get run details")
def get_run(
    request: Request,
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    run = svc.get_run(ctx.active_workspace_id, run_id)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": ReconciliationRunResponse.model_validate(run).model_dump(mode="json"),
            "request_id": request_id,
        },
    )


@router.get("/{run_id}/matches", summary="List match candidates")
def list_matches(
    request: Request,
    run_id: uuid.UUID,
    status: Optional[str] = Query(None),
    min_confidence: Optional[int] = Query(None, ge=0, le=100),
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
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": [MatchCandidateResponse.model_validate(m).model_dump(mode="json") for m in matches],
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            "request_id": request_id,
        },
    )


@router.get("/{run_id}/matches/{match_id}/evidence", summary="Get evidence for a match candidate")
def get_match_evidence(
    run_id: uuid.UUID,
    match_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ReconciliationService(db)
    result = svc.get_match_evidence(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        match_id=match_id,
    )
    return JSONResponse(
        status_code=200,
        content={"data": result},
    )


@router.get("/{run_id}/exceptions", summary="List exceptions")
def list_exceptions(
    request: Request,
    run_id: uuid.UUID,
    status: Optional[str] = Query(None),
    exception_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = ReconciliationRepository(db)
    offset = (page - 1) * page_size
    exceptions, total = repo.list_exceptions(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        status=status,
        exception_type=exception_type,
        limit=page_size,
        offset=offset,
    )
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": [ExceptionItemResponse.model_validate(e).model_dump(mode="json") for e in exceptions],
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            "request_id": request_id,
        },
    )


@router.post("/{run_id}/matches/{match_id}/review", summary="Review a match candidate")
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
        note=payload.note,
        user_id=ctx.user_id,
    )
    return JSONResponse(
        status_code=200,
        content={"data": MatchCandidateResponse.model_validate(match).model_dump(mode="json")},
    )


@router.post("/{run_id}/exceptions/{exception_id}/resolve", summary="Resolve an exception")
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
        note=payload.note,
        user_id=ctx.user_id,
    )
    return JSONResponse(
        status_code=200,
        content={"data": ExceptionItemResponse.model_validate(exc).model_dump(mode="json")},
    )