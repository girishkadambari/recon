"""
Export routes.

POST /api/reconciliations/{run_id}/export          — Generate XLSX export
GET  /api/reconciliations/{run_id}/export          — List export jobs for run
GET  /api/reconciliations/{run_id}/export/{job_id}/download — Stream XLSX file
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUserContext, get_current_user_context
from app.dependencies import get_db
from app.domain.enums.export_enums import ExportScope
from app.domain.services.export_service import ExportService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/reconciliations", tags=["exports"])


@router.post("/{run_id}/export", summary="Generate XLSX export for a completed run")
def create_export(
    run_id: uuid.UUID,
    scope: ExportScope = Query(ExportScope.FULL, description="FULL | MATCHES_ONLY | EXCEPTIONS_ONLY"),
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Generates and stores an XLSX report with three sheets:
    - Summary (run stats + match rate)
    - Matches (confidence, strategy, deltas)
    - Exceptions (reason, AI explanation)

    Run must be COMPLETED. Export is synchronous — file is ready immediately.
    """
    svc = ExportService(db)
    job = svc.create_and_run(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        user_id=ctx.user_id,
        export_scope=scope,
    )
    return JSONResponse(status_code=201, content={"data": job})


@router.get("/{run_id}/export", summary="List export jobs for a run")
def list_exports(
    run_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = ExportService(db)
    jobs = svc.list_jobs(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
    )
    return JSONResponse(status_code=200, content={"data": jobs})


@router.get(
    "/{run_id}/export/{job_id}/download",
    summary="Download an XLSX export file",
)
def download_export(
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Response:
    """
    Streams the XLSX file directly.
    Content-Disposition: attachment causes browser to download it.
    """
    svc = ExportService(db)
    file_bytes, file_name, content_type = svc.download(
        workspace_id=ctx.active_workspace_id,
        run_id=run_id,
        job_id=job_id,
    )
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(len(file_bytes)),
        },
    )
