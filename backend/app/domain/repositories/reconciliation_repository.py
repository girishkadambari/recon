"""
ReconciliationRepository — CRUD for runs, run files, match candidates, exception items.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.dates import utcnow
from app.domain.enums.reconciliation_enums import (
    ExceptionStatus,
    MatchStatus,
    ReconciliationRunStatus,
)
from app.domain.models.reconciliation_models import (
    ExceptionItem,
    MatchCandidate,
    ReconciliationRunFile,
)
from app.domain.models.reconciliation_run import ReconciliationRun
from app.domain.services.matching_engine import EngineOutput, ExceptionResult, MatchResult


class ReconciliationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Runs ──────────────────────────────────────────────────────────

    def create_run(
        self,
        workspace_id: uuid.UUID,
        name: str,
        created_by_user_id: uuid.UUID,
    ) -> ReconciliationRun:
        run = ReconciliationRun(
            workspace_id=workspace_id,
            name=name,
            status=ReconciliationRunStatus.PENDING,
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get_run(self, run_id: uuid.UUID, workspace_id: uuid.UUID) -> ReconciliationRun | None:
        return (
            self.db.query(ReconciliationRun)
            .filter(
                ReconciliationRun.id == run_id,
                ReconciliationRun.workspace_id == workspace_id,
            )
            .first()
        )

    def list_runs(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ReconciliationRun], int]:
        q = self.db.query(ReconciliationRun).filter(
            ReconciliationRun.workspace_id == workspace_id
        )
        total = q.count()
        rows = q.order_by(ReconciliationRun.created_at.desc()).offset(offset).limit(limit).all()
        return rows, total

    def update_run_status(
        self,
        run: ReconciliationRun,
        status: str,
        error_message: str | None = None,
    ) -> ReconciliationRun:
        run.status = status
        if error_message:
            run.error_message = error_message
        if status == ReconciliationRunStatus.COMPLETED:
            run.completed_at = utcnow()
        run.updated_at = utcnow()
        self.db.flush()
        return run

    def update_run_counts(
        self,
        run: ReconciliationRun,
        output: EngineOutput,
    ) -> ReconciliationRun:
        run.total_source_rows = output.total_source
        run.total_target_rows = output.total_target
        run.matched_count = output.matched_count
        run.exception_count = output.exception_count
        run.match_rate_pct = output.match_rate_pct
        run.run_date = utcnow()
        run.updated_at = utcnow()
        self.db.flush()
        return run

    # ── Run Files ─────────────────────────────────────────────────────

    def add_run_file(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        uploaded_file_id: uuid.UUID,
        file_role: str,
        created_by_user_id: uuid.UUID,
    ) -> ReconciliationRunFile:
        rf = ReconciliationRunFile(
            workspace_id=workspace_id,
            run_id=run_id,
            uploaded_file_id=uploaded_file_id,
            file_role=file_role,
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        self.db.add(rf)
        self.db.flush()
        return rf

    def get_run_files(self, run_id: uuid.UUID, workspace_id: uuid.UUID) -> list[ReconciliationRunFile]:
        return (
            self.db.query(ReconciliationRunFile)
            .filter(
                ReconciliationRunFile.run_id == run_id,
                ReconciliationRunFile.workspace_id == workspace_id,
            )
            .all()
        )

    # ── Bulk insert matches ───────────────────────────────────────────

    def bulk_insert_matches(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        matches: list[MatchResult],
        created_by_user_id: uuid.UUID,
    ) -> int:
        if not matches:
            return 0
        import uuid as uuid_lib
        now = utcnow()
        rows = [
            {
                "id": uuid_lib.uuid4(),
                "workspace_id": workspace_id,
                "run_id": run_id,
                "source_record_id": m.source_record_id,
                "source_table": m.source_table,
                "target_record_id": m.target_record_id,
                "target_table": m.target_table,
                "confidence_score": m.confidence_score,
                "match_strategy": m.match_strategy,
                "status": m.status,
                "amount_delta": m.amount_delta,
                "date_delta_days": m.date_delta_days,
                "created_at": now,
                "updated_at": now,
                "created_by_user_id": created_by_user_id,
                "updated_by_user_id": created_by_user_id,
            }
            for m in matches
        ]
        self.db.bulk_insert_mappings(MatchCandidate, rows)
        self.db.flush()
        return len(rows)

    # ── Bulk insert exceptions ────────────────────────────────────────

    def bulk_insert_exceptions(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        exceptions: list[ExceptionResult],
        created_by_user_id: uuid.UUID,
    ) -> int:
        if not exceptions:
            return 0
        import uuid as uuid_lib
        now = utcnow()
        rows = [
            {
                "id": uuid_lib.uuid4(),
                "workspace_id": workspace_id,
                "run_id": run_id,
                "record_id": e.record_id,
                "record_table": e.record_table,
                "file_role": e.file_role,
                "reason": e.reason,
                "status": ExceptionStatus.OPEN,
                "amount": e.amount,
                "currency": e.currency,
                "details_json": e.details_json,
                "created_at": now,
                "updated_at": now,
                "created_by_user_id": created_by_user_id,
                "updated_by_user_id": created_by_user_id,
            }
            for e in exceptions
        ]
        self.db.bulk_insert_mappings(ExceptionItem, rows)
        self.db.flush()
        return len(rows)

    # ── Query matches ─────────────────────────────────────────────────

    def list_matches(
        self,
        run_id: uuid.UUID,
        workspace_id: uuid.UUID,
        status: str | None = None,
        min_confidence: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MatchCandidate], int]:
        q = self.db.query(MatchCandidate).filter(
            MatchCandidate.run_id == run_id,
            MatchCandidate.workspace_id == workspace_id,
        )
        if status:
            q = q.filter(MatchCandidate.status == status)
        if min_confidence:
            q = q.filter(MatchCandidate.confidence_score >= min_confidence)
        total = q.count()
        rows = q.order_by(MatchCandidate.confidence_score.desc()).offset(offset).limit(limit).all()
        return rows, total

    def get_match(self, match_id: uuid.UUID, run_id: uuid.UUID, workspace_id: uuid.UUID) -> MatchCandidate | None:
        return (
            self.db.query(MatchCandidate)
            .filter(
                MatchCandidate.id == match_id,
                MatchCandidate.run_id == run_id,
                MatchCandidate.workspace_id == workspace_id,
            )
            .first()
        )

    def update_match_status(
        self,
        match: MatchCandidate,
        status: str,
        reviewed_by_user_id: uuid.UUID,
        review_note: str | None = None,
    ) -> MatchCandidate:
        match.status = status
        match.reviewed_by_user_id = reviewed_by_user_id
        match.review_note = review_note
        match.updated_at = utcnow()
        self.db.flush()
        return match

    # ── Query exceptions ──────────────────────────────────────────────

    def list_exceptions(
        self,
        run_id: uuid.UUID,
        workspace_id: uuid.UUID,
        status: str | None = None,
        reason: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ExceptionItem], int]:
        q = self.db.query(ExceptionItem).filter(
            ExceptionItem.run_id == run_id,
            ExceptionItem.workspace_id == workspace_id,
        )
        if status:
            q = q.filter(ExceptionItem.status == status)
        if reason:
            q = q.filter(ExceptionItem.reason == reason)
        total = q.count()
        rows = q.order_by(ExceptionItem.created_at.asc()).offset(offset).limit(limit).all()
        return rows, total

    def get_exception(self, exception_id: uuid.UUID, run_id: uuid.UUID, workspace_id: uuid.UUID) -> ExceptionItem | None:
        return (
            self.db.query(ExceptionItem)
            .filter(
                ExceptionItem.id == exception_id,
                ExceptionItem.run_id == run_id,
                ExceptionItem.workspace_id == workspace_id,
            )
            .first()
        )

    def update_exception(
        self,
        exception: ExceptionItem,
        status: str,
        resolved_by_user_id: uuid.UUID,
        resolution_note: str | None = None,
    ) -> ExceptionItem:
        exception.status = status
        exception.resolved_by_user_id = resolved_by_user_id
        exception.resolution_note = resolution_note
        exception.updated_at = utcnow()
        self.db.flush()
        return exception
