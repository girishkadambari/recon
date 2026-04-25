"""
Upload routes.

POST   /api/uploads                     — Upload a file (multipart/form-data)
GET    /api/uploads                     — List uploads for workspace
GET    /api/uploads/{file_id}           — Get upload details
GET    /api/uploads/{file_id}/preview   — Preview parsed rows
DELETE /api/uploads/{file_id}           — Soft delete
"""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.core.errors import NotFoundError
from app.dependencies import get_db
from app.domain.enums.file_enums import FileCategory
from app.domain.schemas.upload_schemas import UploadedFileResponse, PreviewResponse
from app.domain.services.file_ingestion_service import FileIngestionService
from app.domain.repositories.source_record_repository import SourceRecordRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/uploads", tags=["uploads"])

ALLOWED_CATEGORIES = {c.value for c in FileCategory}


@router.post("", summary="Upload a CSV or XLSX file")
async def upload_file(
    file: UploadFile = File(...),
    file_category: str = Form(..., description="One of: " + ", ".join(ALLOWED_CATEGORIES)),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Accepts multipart/form-data with:
      - file: the CSV or XLSX file
      - file_category: category label (e.g. STRIPE_REPORT)

    Returns the created UploadedFile record. Parsing happens synchronously in the MVP.
    """
    if file_category not in ALLOWED_CATEGORIES:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_FILE_CATEGORY",
                    "message": f"Invalid file_category '{file_category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}",
                    "details": {},
                }
            },
        )

    file_bytes = await file.read()
    mime_type = file.content_type

    svc = FileIngestionService(db)
    uploaded_file = svc.ingest_file(
        workspace_id=ctx.active_workspace_id,
        user_id=ctx.user_id,
        file_name=file.filename or "upload",
        file_bytes=file_bytes,
        file_category=file_category,
        mime_type=mime_type,
    )

    return JSONResponse(
        status_code=201,
        content={
            "data": UploadedFileResponse.model_validate(uploaded_file).model_dump(mode="json")
        },
    )


@router.get("", summary="List uploaded files")
def list_uploads(
    file_category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = FileIngestionService(db)
    files, total = svc.list_files(
        workspace_id=ctx.active_workspace_id,
        file_category=file_category,
        page=page,
        page_size=page_size,
    )
    return JSONResponse(
        status_code=200,
        content={
            "data": [UploadedFileResponse.model_validate(f).model_dump(mode="json") for f in files],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
            "has_prev": page > 1,
        },
    )


@router.get("/{file_id}", summary="Get upload details")
def get_upload(
    file_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = FileIngestionService(db)
    uf = svc.get_file(ctx.active_workspace_id, file_id)
    return JSONResponse(
        status_code=200,
        content={"data": UploadedFileResponse.model_validate(uf).model_dump(mode="json")},
    )


@router.get("/{file_id}/preview", summary="Preview parsed rows")
def preview_upload(
    file_id: uuid.UUID,
    n: int = Query(20, ge=1, le=200, description="Number of rows to preview"),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = FileIngestionService(db)
    uf = svc.get_file(ctx.active_workspace_id, file_id)

    source_repo = SourceRecordRepository(db)
    records = source_repo.list_for_file(
        workspace_id=ctx.active_workspace_id,
        uploaded_file_id=file_id,
        limit=n,
    )
    total = uf.row_count or 0
    rows = [r.raw_data_json for r in records]
    column_names = list(rows[0].keys()) if rows else []

    return JSONResponse(
        status_code=200,
        content={
            "data": {
                "file_id": str(uf.id),
                "file_name": uf.file_name,
                "file_category": uf.file_category,
                "column_names": column_names,
                "rows": rows,
                "total_rows": total,
                "preview_count": len(rows),
            }
        },
    )


@router.delete("/{file_id}", summary="Soft delete an uploaded file")
def delete_upload(
    file_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = FileIngestionService(db)
    svc.delete_file(ctx.active_workspace_id, file_id, ctx.user_id)
    return JSONResponse(
        status_code=200,
        content={"data": {"message": f"File {file_id} deleted."}},
    )
