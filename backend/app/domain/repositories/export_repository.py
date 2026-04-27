"""
ExportRepository — CRUD for export_jobs.
"""
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.core.dates import utcnow
from app.domain.enums.export_enums import ExportStatus
from app.domain.models.export_job import ExportJob


class ExportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        export_scope: str,
        created_by_user_id: uuid.UUID,
    ) -> ExportJob:
        job = ExportJob(
            workspace_id=workspace_id,
            run_id=run_id,
            export_scope=export_scope,
            status=ExportStatus.PENDING,
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: uuid.UUID, workspace_id: uuid.UUID) -> Optional[ExportJob]:
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.id == job_id,
                ExportJob.workspace_id == workspace_id,
            )
            .first()
        )

    def get_latest_for_run(
        self, run_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[ExportJob]:
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.run_id == run_id,
                ExportJob.workspace_id == workspace_id,
                ExportJob.status == ExportStatus.COMPLETED,
            )
            .order_by(ExportJob.created_at.desc())
            .first()
        )

    def list_for_run(
        self, run_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[ExportJob]:
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.run_id == run_id,
                ExportJob.workspace_id == workspace_id,
            )
            .order_by(ExportJob.created_at.desc())
            .all()
        )

    def list_all(
        self, workspace_id: uuid.UUID
    ) -> list[ExportJob]:
        return (
            self.db.query(ExportJob)
            .filter(
                ExportJob.workspace_id == workspace_id,
            )
            .order_by(ExportJob.created_at.desc())
            .all()
        )

    def mark_in_progress(self, job: ExportJob) -> ExportJob:
        job.status = ExportStatus.IN_PROGRESS
        job.updated_at = utcnow()
        self.db.flush()
        return job

    def mark_completed(
        self,
        job: ExportJob,
        storage_key: str,
        file_name: str,
        file_size_bytes: int,
        matched_rows_exported: int,
        exception_rows_exported: int,
    ) -> ExportJob:
        job.status = ExportStatus.COMPLETED
        job.storage_key = storage_key
        job.file_name = file_name
        job.file_size_bytes = file_size_bytes
        job.matched_rows_exported = matched_rows_exported
        job.exception_rows_exported = exception_rows_exported
        job.updated_at = utcnow()
        self.db.flush()
        return job

    def mark_failed(self, job: ExportJob, error: str) -> ExportJob:
        job.status = ExportStatus.FAILED
        job.error_message = error
        job.updated_at = utcnow()
        self.db.flush()
        return job