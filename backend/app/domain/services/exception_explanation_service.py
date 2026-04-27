"""
ExceptionExplanationService — orchestrates AI explanations for reconciliation exceptions.

Business logic:
  - explain_one():   Generate explanation for a single ExceptionItem
  - explain_all():   Batch explain all OPEN exceptions in a run (rate-limited)
  - run_summary():   Generate executive AI summary for an entire run
  
AI is purely advisory — explanations are stored in ExceptionItem.ai_explanation
but never affect match status or exception resolution.
"""
from __future__ import annotations
from typing import Optional
import uuid
from collections import Counter
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ConflictError
from app.domain.enums.reconciliation_enums import ExceptionStatus, ReconciliationRunStatus
from app.domain.models.reconciliation_models import ExceptionItem, MatchCandidate
from app.domain.models.reconciliation_run import ReconciliationRun
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.repositories.uploaded_file_repository import UploadedFileRepository
from app.core.dates import utcnow

logger = structlog.get_logger(__name__)

# Max exceptions to explain in one batch call (cost guard)
BATCH_EXPLAIN_LIMIT = 50


class ExceptionExplanationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.recon_repo = ReconciliationRepository(db)
        self.file_repo = UploadedFileRepository(db)

    def explain_one(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        exception_id: uuid.UUID,
        user_id: uuid.UUID,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Generate (or return cached) AI explanation for a single exception.
        Stores the explanation text in ExceptionItem.ai_explanation.
        """
        run = self._get_run(workspace_id, run_id)
        exc = self.recon_repo.get_exception(exception_id, run_id, workspace_id)
        if not exc:
            raise NotFoundError(f"Exception {exception_id} not found.")

        # Return cached explanation if present and not forcing refresh
        if exc.ai_explanation and not force_refresh:
            return {
                "exception_id": str(exception_id),
                "ai_explanation": exc.ai_explanation,
                "cached": True,
            }

        context = self._build_exception_context(run, exc)
        from app.ai.services.ai_exception_service import explain_exception
        result = explain_exception(**context)

        # Persist the explanation in the DB
        explanation_text = self._format_explanation(result)
        self._save_explanation(exc, explanation_text)
        self.db.commit()

        logger.info(
            "Exception explanation generated",
            exception_id=str(exception_id),
            confidence=result.get("confidence"),
        )
        return {
            "exception_id": str(exception_id),
            "explanation": result["explanation"],
            "probable_cause": result["probable_cause"],
            "recommended_action": result["recommended_action"],
            "confidence": result["confidence"],
            "cached": False,
        }

    def explain_all_open(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Batch-explain all OPEN exceptions in a run.
        Skips already-explained exceptions.
        Caps at BATCH_EXPLAIN_LIMIT to control cost.
        """
        run = self._get_run(workspace_id, run_id)
        if run.status != ReconciliationRunStatus.COMPLETED:
            raise ConflictError("Run must be COMPLETED before generating explanations.")

        open_exceptions, _ = self.recon_repo.list_exceptions(
            run_id=run_id,
            workspace_id=workspace_id,
            status=ExceptionStatus.OPEN,
            limit=BATCH_EXPLAIN_LIMIT,
        )

        to_explain = [e for e in open_exceptions if not e.ai_explanation]
        if not to_explain:
            return {
                "run_id": str(run_id),
                "explained": 0,
                "skipped": len(open_exceptions),
                "message": "All open exceptions already have explanations.",
            }

        from app.ai.services.ai_exception_service import explain_exception
        explained_count = 0
        errors: list[str] = []

        for exc in to_explain:
            try:
                context = self._build_exception_context(run, exc)
                result = explain_exception(**context)
                explanation_text = self._format_explanation(result)
                self._save_explanation(exc, explanation_text)
                explained_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to explain exception",
                    exception_id=str(exc.id),
                    error=str(e),
                )
                errors.append(str(exc.id))

        self.db.commit()

        logger.info(
            "Batch exception explanation complete",
            run_id=str(run_id),
            explained=explained_count,
            errors=len(errors),
        )
        return {
            "run_id": str(run_id),
            "explained": explained_count,
            "skipped": len(open_exceptions) - len(to_explain),
            "failed": len(errors),
            "capped_at": BATCH_EXPLAIN_LIMIT,
        }

    def generate_run_summary(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Generate an AI executive summary for the entire reconciliation run.
        Not stored — always generated fresh.
        """
        run = self._get_run(workspace_id, run_id)
        if run.status != ReconciliationRunStatus.COMPLETED:
            raise ConflictError("Run must be COMPLETED before generating a summary.")

        # Gather context: exception breakdown, strategy breakdown
        all_exceptions, _ = self.recon_repo.list_exceptions(
            run_id=run_id, workspace_id=workspace_id, limit=500
        )
        exception_breakdown = dict(Counter(e.exception_type for e in all_exceptions))

        all_matches, _ = self.recon_repo.list_matches(
            run_id=run_id, workspace_id=workspace_id, limit=5000
        )
        strategy_breakdown = dict(Counter(m.match_strategy for m in all_matches))

        # Get file category names for context
        run_files = self.recon_repo.get_run_files(run_id, workspace_id)
        src_rf = next((rf for rf in run_files if rf.file_role == "SOURCE"), None)
        tgt_rf = next((rf for rf in run_files if rf.file_role == "TARGET"), None)

        src_category = self._get_file_category(workspace_id, src_rf.uploaded_file_id if src_rf else None)
        tgt_category = self._get_file_category(workspace_id, tgt_rf.uploaded_file_id if tgt_rf else None)

        from app.ai.services.ai_exception_service import generate_run_summary
        result = generate_run_summary(
            run_name=run.name,
            completed_at=run.completed_at.isoformat() if run.completed_at else "N/A",
            source_category=src_category,
            target_category=tgt_category,
            total_source_rows=run.total_source_rows,
            total_target_rows=run.total_target_rows,
            matched_count=run.matched_count,
            match_rate_pct=run.match_rate_pct or 0,
            exception_count=run.exception_count,
            exception_breakdown=exception_breakdown,
            strategy_breakdown=strategy_breakdown,
        )

        return {
            "run_id": str(run_id),
            "run_name": run.name,
            "match_rate_pct": run.match_rate_pct,
            **result,
        }

    # ── Private ───────────────────────────────────────────────────────

    def _get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> ReconciliationRun:
        run = self.recon_repo.get_run(run_id, workspace_id)
        if not run:
            raise NotFoundError(f"ReconciliationRun {run_id} not found.")
        return run

    def _build_exception_context(
        self, run: ReconciliationRun, exc: ExceptionItem
    ) -> dict[str, Any]:
        """Build the context dict for the AI explain_exception call."""
        run_files = self.recon_repo.get_run_files(run.id, run.workspace_id)
        src_rf = next((rf for rf in run_files if rf.file_role == "SOURCE"), None)
        tgt_rf = next((rf for rf in run_files if rf.file_role == "TARGET"), None)

        src_cat = self._get_file_category(run.workspace_id, src_rf.uploaded_file_id if src_rf else None)
        tgt_cat = self._get_file_category(run.workspace_id, tgt_rf.uploaded_file_id if tgt_rf else None)

        return {
            "run_name": run.name,
            "source_category": src_cat,
            "target_category": tgt_cat,
            "match_rate_pct": run.match_rate_pct or 0,
            "file_role": exc.file_role,
            "reason_code": exc.exception_type,
            "severity": exc.severity,
            "amount": str(exc.amount) if exc.amount else "N/A",
            "currency": exc.currency,
            "record_data": exc.details_json or {},
        }

    def _get_file_category(self, workspace_id: uuid.UUID, file_id: Optional[uuid.UUID]) -> str:
        if not file_id:
            return "Unknown"
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        return uf.file_category if uf else "Unknown"

    def _format_explanation(self, result: dict[str, Any]) -> str:
        """Format the AI result into a single stored text string."""
        return (
            f"{result['explanation']}\n\n"
            f"Probable cause: {result['probable_cause']}\n"
            f"Recommended action: {result['recommended_action']}\n"
            f"AI confidence: {result['confidence']}"
        )

    def _save_explanation(self, exc: ExceptionItem, explanation_text: str) -> None:
        exc.ai_explanation = explanation_text
        exc.updated_at = utcnow()
        self.db.flush()