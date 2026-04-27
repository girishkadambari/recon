"""
Column mapping and normalization routes.

POST   /api/column-mappings/{file_id}/suggest    — Ask AI to suggest mapping
GET    /api/column-mappings/{file_id}            — Get current mapping
POST   /api/column-mappings/{file_id}/confirm    — Confirm (optionally edit) mapping
POST   /api/column-mappings/{file_id}/normalize  — Run normalization
GET    /api/column-mappings/{file_id}/rows       — Preview canonical rows
"""
import uuid

import structlog
from fastapi import Request, APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.dependencies import get_db
from app.domain.schemas.mapping_schemas import (
    ColumnMappingResponse,
    ConfirmMappingRequest,
)
from app.domain.services.column_mapping_service import ColumnMappingService
from app.domain.services.normalization_service import NormalizationService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/column-mappings", tags=["column-mappings"])


@router.post("/{file_id}/suggest", summary="Ask AI to suggest column mapping")
def suggest_column_mapping(
    request: Request,
    file_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ColumnMappingService(db)
    mapping = svc.suggest_mapping(
        workspace_id=ctx.active_workspace_id,
        file_id=file_id,
        user_id=ctx.user_id,
    )
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": ColumnMappingResponse.model_validate(mapping).model_dump(mode="json"),
            "request_id": request_id,
        },
    )


@router.get("/{file_id}", summary="Get column mapping for a file")
def get_column_mapping(
    request: Request,
    file_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ColumnMappingService(db)
    mapping = svc.get_mapping(ctx.active_workspace_id, file_id)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": ColumnMappingResponse.model_validate(mapping).model_dump(mode="json"),
            "request_id": request_id,
        },
    )


@router.post("/{file_id}/confirm", summary="Confirm (and optionally edit) column mapping")
def confirm_column_mapping(
    request: Request,
    file_id: uuid.UUID,
    payload: ConfirmMappingRequest = ConfirmMappingRequest(),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ColumnMappingService(db)
    mapping = svc.confirm_mapping(
        workspace_id=ctx.active_workspace_id,
        file_id=file_id,
        user_id=ctx.user_id,
        updated_mapping=payload.mapping,
    )
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": ColumnMappingResponse.model_validate(mapping).model_dump(mode="json"),
            "request_id": request_id,
        },
    )


@router.post("/{file_id}/normalize", summary="Run normalization for a confirmed mapping")
def normalize_file(
    request: Request,
    file_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = NormalizationService(db)
    result = svc.normalize_file(
        workspace_id=ctx.active_workspace_id,
        file_id=file_id,
        user_id=ctx.user_id,
    )
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": result,
            "request_id": request_id,
        },
    )


@router.get("/{file_id}/rows", summary="Preview canonical rows")
def get_canonical_rows(
    request: Request,
    file_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = NormalizationService(db)
    offset = (page - 1) * page_size
    rows, table_name = svc.get_canonical_rows(
        workspace_id=ctx.active_workspace_id,
        file_id=file_id,
        limit=page_size,
        offset=offset,
    )

    def _serialize(obj) -> dict:
        serialized = {}
        for col in obj.__class__.__table__.columns:
            val = getattr(obj, col.name)
            if hasattr(val, "isoformat"):
                serialized[col.name] = val.isoformat()
            elif hasattr(val, "__str__") and not isinstance(val, (str, int, float, bool, type(None))):
                serialized[col.name] = str(val)
            else:
                serialized[col.name] = val
        return serialized

    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=200,
        content={
            "data": {
                "file_id": str(file_id),
                "canonical_table": table_name,
                "rows": [_serialize(r) for r in rows],
                "count": len(rows),
                "page": page,
            },
            "request_id": request_id,
        },
    )
