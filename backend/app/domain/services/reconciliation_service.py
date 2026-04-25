"""
ReconciliationService — orchestrates a full reconciliation run.

Flow:
  1. Create ReconciliationRun with SOURCE and TARGET files
  2. Load canonical records for each file from the DB
  3. Run MatchingEngine (deterministic, no AI)
  4. Bulk insert MatchCandidates and ExceptionItems
  5. Update run counters + status = COMPLETED

No AI here. AI explanations for exceptions are in Phase 5 (ExceptionService).
"""
import uuid
from typing import Any

import structlog
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.domain.enums.audit_enums import AuditEventType
from app.domain.enums.mapping_enums import NormalizationStatus
from app.domain.enums.reconciliation_enums import (
    ExceptionStatus,
    FileRole,
    MatchStatus,
    ReconciliationRunStatus,
)
from app.domain.models.reconciliation_models import ExceptionItem, MatchCandidate
from app.domain.models.reconciliation_run import ReconciliationRun
from app.domain.repositories.column_mapping_repository import ColumnMappingRepository
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.repositories.uploaded_file_repository import UploadedFileRepository
from app.domain.services.audit_service import AuditService
from app.domain.services.matching_engine import MatchingEngine
from app.domain.services.normalization_service import CATEGORY_MODEL_MAP

logger = structlog.get_logger(__name__)

# Load canonical rows in batches
LOAD_BATCH_SIZE = 5000


class ReconciliationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.recon_repo = ReconciliationRepository(db)
        self.file_repo = UploadedFileRepository(db)
        self.mapping_repo = ColumnMappingRepository(db)
        self.audit_svc = AuditService(db)

    def create_run(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        source_file_id: uuid.UUID,
        target_file_id: uuid.UUID,
    ) -> ReconciliationRun:
        """
        Create a reconciliation run for two normalized files.
        Validates that both files belong to the workspace and are normalized.
        """
        # Validate files
        src_file = self._get_validated_file(workspace_id, source_file_id, "source")
        tgt_file = self._get_validated_file(workspace_id, target_file_id, "target")

        run = self.recon_repo.create_run(
            workspace_id=workspace_id,
            name=name,
            created_by_user_id=user_id,
        )
        self.recon_repo.add_run_file(
            workspace_id=workspace_id,
            run_id=run.id,
            uploaded_file_id=source_file_id,
            file_role=FileRole.SOURCE,
            created_by_user_id=user_id,
        )
        self.recon_repo.add_run_file(
            workspace_id=workspace_id,
            run_id=run.id,
            uploaded_file_id=target_file_id,
            file_role=FileRole.TARGET,
            created_by_user_id=user_id,
        )
        self.db.commit()
        return run

    def execute_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ReconciliationRun:
        """
        Execute the matching engine for a run.
        """
        run = self.recon_repo.get_run(run_id, workspace_id)
        if not run:
            raise NotFoundError(f"ReconciliationRun {run_id} not found.")
        if run.status == ReconciliationRunStatus.COMPLETED:
            raise ConflictError(f"Run {run_id} is already completed.")
        if run.status == ReconciliationRunStatus.IN_PROGRESS:
            raise ConflictError(f"Run {run_id} is already in progress.")

        # Mark as IN_PROGRESS
        self.recon_repo.update_run_status(run, ReconciliationRunStatus.IN_PROGRESS)
        self.db.flush()

        self.audit_svc.log(
            event_type=AuditEventType.RECONCILIATION_STARTED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="reconciliation_run",
            entity_id=run_id,
            metadata={"run_name": run.name},
        )

        try:
            # Load file assignments
            run_files = self.recon_repo.get_run_files(run_id, workspace_id)
            src_rf = next((rf for rf in run_files if rf.file_role == FileRole.SOURCE), None)
            tgt_rf = next((rf for rf in run_files if rf.file_role == FileRole.TARGET), None)
            if not src_rf or not tgt_rf:
                raise ConflictError("Run must have both SOURCE and TARGET files.")

            # Load canonical records
            src_records, src_table = self._load_canonical_records(workspace_id, src_rf.uploaded_file_id)
            tgt_records, tgt_table = self._load_canonical_records(workspace_id, tgt_rf.uploaded_file_id)

            logger.info(
                "Reconciliation starting",
                run_id=str(run_id),
                source_rows=len(src_records),
                target_rows=len(tgt_records),
            )

            # Run the deterministic engine
            engine = MatchingEngine()
            output = engine.run(
                source_records=src_records,
                target_records=tgt_records,
                source_table=src_table,
                target_table=tgt_table,
            )

            # Persist results
            self.recon_repo.bulk_insert_matches(
                workspace_id=workspace_id,
                run_id=run_id,
                matches=output.matches,
                created_by_user_id=user_id,
            )
            self.recon_repo.bulk_insert_exceptions(
                workspace_id=workspace_id,
                run_id=run_id,
                exceptions=output.exceptions,
                created_by_user_id=user_id,
            )
            self.recon_repo.update_run_counts(run, output)
            self.recon_repo.update_run_status(run, ReconciliationRunStatus.COMPLETED)

            self.audit_svc.log(
                event_type=AuditEventType.RECONCILIATION_COMPLETED,
                actor_user_id=user_id,
                workspace_id=workspace_id,
                entity_type="reconciliation_run",
                entity_id=run_id,
                metadata={
                    "matched": output.matched_count,
                    "exceptions": output.exception_count,
                    "match_rate_pct": output.match_rate_pct,
                },
            )
            self.db.commit()

            logger.info(
                "Reconciliation completed",
                run_id=str(run_id),
                matched=output.matched_count,
                exceptions=output.exception_count,
                match_rate=output.match_rate_pct,
            )
            return run

        except Exception as exc:
            self.recon_repo.update_run_status(
                run, ReconciliationRunStatus.FAILED, error_message=str(exc)
            )
            self.db.commit()
            logger.error("Reconciliation failed", run_id=str(run_id), error=str(exc))
            raise

    def _load_canonical_records(
        self, workspace_id: uuid.UUID, file_id: uuid.UUID
    ) -> tuple[list[dict], str]:
        """Load all canonical rows for a file as plain dicts."""
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"File {file_id} not found.")
        model_cls = CATEGORY_MODEL_MAP.get(uf.file_category)
        if not model_cls:
            raise ConflictError(
                f"No canonical table for '{uf.file_category}'. Normalize the file first."
            )

        # Load in batches
        records: list[dict] = []
        offset = 0
        while True:
            batch = (
                self.db.query(model_cls)
                .filter(
                    model_cls.workspace_id == workspace_id,
                    model_cls.uploaded_file_id == file_id,
                )
                .order_by(model_cls.row_number)
                .offset(offset)
                .limit(LOAD_BATCH_SIZE)
                .all()
            )
            if not batch:
                break
            for row in batch:
                records.append(_model_to_dict(row))
            offset += LOAD_BATCH_SIZE

        return records, model_cls.__tablename__

    def _get_validated_file(self, workspace_id: uuid.UUID, file_id: uuid.UUID, role: str):
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"{role} file {file_id} not found.")
        # Check normalization is complete
        mapping = self.mapping_repo.get_by_file_id(file_id, workspace_id)
        if not mapping or mapping.normalization_status != NormalizationStatus.COMPLETED:
            raise ConflictError(
                f"{role} file {file_id} has not been normalized. "
                "Complete column mapping and normalization first."
            )
        return uf

    def get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> ReconciliationRun:
        run = self.recon_repo.get_run(run_id, workspace_id)
        if not run:
            raise NotFoundError(f"ReconciliationRun {run_id} not found.")
        return run

    def list_runs(
        self, workspace_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReconciliationRun], int]:
        offset = (page - 1) * page_size
        return self.recon_repo.list_runs(workspace_id, limit=page_size, offset=offset)

    def review_match(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        match_id: uuid.UUID,
        action: str,
        user_id: uuid.UUID,
        note: str | None = None,
    ) -> MatchCandidate:
        if action not in (MatchStatus.APPROVED, MatchStatus.REJECTED):
            raise ConflictError(f"Invalid action '{action}'. Use APPROVED or REJECTED.")
        match = self.recon_repo.get_match(match_id, run_id, workspace_id)
        if not match:
            raise NotFoundError(f"Match {match_id} not found.")
        match = self.recon_repo.update_match_status(match, action, user_id, note)
        event_type = AuditEventType.MATCH_APPROVED if action == MatchStatus.APPROVED else AuditEventType.MATCH_REJECTED
        self.audit_svc.log(
            event_type=event_type,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="match_candidate",
            entity_id=match_id,
            metadata={"run_id": str(run_id), "note": note},
        )
        self.db.commit()
        return match

    def resolve_exception(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        exception_id: uuid.UUID,
        status: str,
        user_id: uuid.UUID,
        note: str | None = None,
    ) -> ExceptionItem:
        if status not in (ExceptionStatus.RESOLVED, ExceptionStatus.WAIVED):
            raise ConflictError(f"Invalid status '{status}'. Use RESOLVED or WAIVED.")
        exc = self.recon_repo.get_exception(exception_id, run_id, workspace_id)
        if not exc:
            raise NotFoundError(f"Exception {exception_id} not found.")
        exc = self.recon_repo.update_exception(exc, status, user_id, note)
        self.audit_svc.log(
            event_type=AuditEventType.EXCEPTION_RESOLVED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="exception_item",
            entity_id=exception_id,
            metadata={"run_id": str(run_id), "status": status, "note": note},
        )
        self.db.commit()
        return exc


def _model_to_dict(obj) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict (including UUID id)."""
    d = {}
    for c in obj.__class__.__table__.columns:
        val = getattr(obj, c.name)
        d[c.name] = val
    return d
