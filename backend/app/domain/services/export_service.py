"""
ExportService — orchestrates XLSX generation, S3 storage, and download.

Flow:
  1. Create ExportJob (PENDING)
  2. Load run + all matches + all exceptions from DB
  3. Build XLSX via XLSXExportBuilder (pure, no DB)
  4. Upload to S3 at exports/{workspace_id}/{run_id}/{job_id}.xlsx
  5. Mark ExportJob COMPLETED with storage key and file size
  6. Download: stream file bytes directly from S3 (no presigned URL needed for MVP)
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.dates import utcnow
from app.core.errors import ConflictError, NotFoundError
from app.domain.enums.audit_enums import AuditEventType
from app.domain.enums.export_enums import ExportScope, ExportStatus
from app.domain.enums.reconciliation_enums import ReconciliationRunStatus
from app.domain.repositories.export_repository import ExportRepository
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.services.audit_service import AuditService
from app.domain.services.xlsx_export_builder import build_xlsx
from app.integrations.storage.s3_client import download_file, upload_file

logger = structlog.get_logger(__name__)

# Load in pages to avoid OOM on large runs
PAGE_SIZE = 5000


class ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.export_repo = ExportRepository(db)
        self.recon_repo = ReconciliationRepository(db)
        self.audit_svc = AuditService(db)

    def create_and_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        export_scope: str = ExportScope.FULL,
    ) -> dict[str, Any]:
        """
        Synchronously generate the XLSX, upload to S3, and return job metadata.
        """
        # Validate run exists and is completed
        run = self.recon_repo.get_run(run_id, workspace_id)
        if not run:
            raise NotFoundError(f"ReconciliationRun {run_id} not found.")
        if run.status != ReconciliationRunStatus.COMPLETED:
            raise ConflictError(
                f"Run {run_id} must be COMPLETED before exporting. Current status: {run.status}"
            )

        # Create job record
        job = self.export_repo.create(
            workspace_id=workspace_id,
            run_id=run_id,
            export_scope=export_scope,
            created_by_user_id=user_id,
        )
        self.export_repo.mark_in_progress(job)
        self.db.flush()

        try:
            # Load data
            matches = self._load_matches(run_id, workspace_id, export_scope)
            exceptions = self._load_exceptions(run_id, workspace_id, export_scope)

            # Serialize to plain dicts
            match_dicts = [_model_to_dict(m) for m in matches]
            exc_dicts = [_model_to_dict(e) for e in exceptions]

            # Build XLSX bytes
            xlsx_bytes = build_xlsx(
                run_name=run.name,
                run_status=run.status,
                run_date=run.run_date.isoformat() if run.run_date else "N/A",
                match_rate_pct=run.match_rate_pct,
                total_source_rows=run.total_source_rows,
                total_target_rows=run.total_target_rows,
                matched_count=run.matched_count,
                exception_count=run.exception_count,
                matches=match_dicts,
                exceptions=exc_dicts,
            )

            # Upload to S3
            storage_key, file_name = _build_export_storage_key(workspace_id, run_id, job.id, run.name)
            upload_file(
                file_bytes=xlsx_bytes,
                storage_key=storage_key,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            # Mark completed
            self.export_repo.mark_completed(
                job=job,
                storage_key=storage_key,
                file_name=file_name,
                file_size_bytes=len(xlsx_bytes),
                matched_rows_exported=len(match_dicts),
                exception_rows_exported=len(exc_dicts),
            )
            self.audit_svc.log(
                event_type=AuditEventType.REPORT_EXPORTED,
                actor_user_id=user_id,
                workspace_id=workspace_id,
                entity_type="export_job",
                entity_id=job.id,
                metadata={
                    "run_id": str(run_id),
                    "file_name": file_name,
                    "file_size_bytes": len(xlsx_bytes),
                    "rows_exported": len(match_dicts) + len(exc_dicts),
                },
            )
            self.db.commit()

            logger.info(
                "Export completed",
                job_id=str(job.id),
                run_id=str(run_id),
                file_name=file_name,
                size_bytes=len(xlsx_bytes),
            )
            return _job_to_dict(job)

        except Exception as exc:
            self.export_repo.mark_failed(job, str(exc))
            self.db.commit()
            logger.error("Export failed", job_id=str(job.id), error=str(exc))
            raise

    def download(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> tuple[bytes, str, str]:
        """
        Download export bytes.
        Returns (file_bytes, file_name, content_type).
        """
        job = self.export_repo.get(job_id, workspace_id)
        if not job:
            raise NotFoundError(f"ExportJob {job_id} not found.")
        if job.run_id != run_id:
            raise NotFoundError(f"ExportJob {job_id} does not belong to run {run_id}.")
        if job.status != ExportStatus.COMPLETED:
            raise ConflictError(f"Export is not ready. Status: {job.status}")

        file_bytes = download_file(job.storage_key)
        return (
            file_bytes,
            job.file_name or f"recon_export.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def list_jobs(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        jobs = self.export_repo.list_for_run(run_id, workspace_id)
        return [_job_to_dict(j) for j in jobs]

    def list_all_jobs(self, workspace_id: uuid.UUID) -> list[dict[str, Any]]:
        jobs = self.export_repo.list_all(workspace_id)
        return [_job_to_dict(j) for j in jobs]

    # ── Private helpers ───────────────────────────────────────────────

    def _load_matches(
        self, run_id: uuid.UUID, workspace_id: uuid.UUID, scope: str
    ) -> list:
        if scope == ExportScope.EXCEPTIONS_ONLY:
            return []
        matches, _ = self.recon_repo.list_matches(
            run_id=run_id,
            workspace_id=workspace_id,
            limit=PAGE_SIZE,
        )
        return matches

    def _load_exceptions(
        self, run_id: uuid.UUID, workspace_id: uuid.UUID, scope: str
    ) -> list:
        if scope == ExportScope.MATCHES_ONLY:
            return []
        exceptions, _ = self.recon_repo.list_exceptions(
            run_id=run_id,
            workspace_id=workspace_id,
            limit=PAGE_SIZE,
        )
        return exceptions


# ── Private functions ─────────────────────────────────────────────────────────

def _build_export_storage_key(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    run_name: str,
) -> tuple[str, str]:
    safe_name = run_name.replace(" ", "_").replace("/", "-")[:50]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    file_name = f"recon_{safe_name}_{ts}.xlsx"
    storage_key = f"exports/{workspace_id}/{run_id}/{job_id}/{file_name}"
    return storage_key, file_name


def _model_to_dict(obj) -> dict[str, Any]:
    d = {}
    for c in obj.__class__.__table__.columns:
        val = getattr(obj, c.name)
        d[c.name] = val
    return d


def _job_to_dict(job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "run_id": str(job.run_id),
        "status": job.status,
        "export_format": job.export_format,
        "export_scope": job.export_scope,
        "file_name": job.file_name,
        "file_size_bytes": job.file_size_bytes,
        "matched_rows_exported": job.matched_rows_exported,
        "exception_rows_exported": job.exception_rows_exported,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
