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
from __future__ import annotations
from typing import Optional
import uuid
from typing import Any

import structlog
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.dates import utcnow
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

    def create_run_multi(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        uploaded_file_ids: list[uuid.UUID],
    ) -> ReconciliationRun:
        """
        Create a reconciliation run for multiple normalized files.
        Auto-detects roles based on file categories.
        """
        if not uploaded_file_ids:
            raise ConflictError("At least one file must be selected.")
            
        validated_files = []
        for fid in uploaded_file_ids:
            uf = self._get_validated_file(workspace_id, fid, "file")
            validated_files.append(uf)

        run = self.recon_repo.create_run(
            workspace_id=workspace_id,
            name=name,
            created_by_user_id=user_id,
        )
        
        for uf in validated_files:
            role = self._detect_file_role(uf.file_category)
            self.recon_repo.add_run_file(
                workspace_id=workspace_id,
                run_id=run.id,
                uploaded_file_id=uf.id,
                file_role=role,
                created_by_user_id=user_id,
            )
            
        self.db.commit()
        return run

    def _detect_file_role(self, category: str) -> FileRole:
        """Map file category to reconciliation role."""
        from app.domain.enums.file_enums import FileCategory
        if category in (FileCategory.CHARGEBEE_INVOICE_EXPORT, FileCategory.INVOICE_EXPORT):
            return FileRole.BILLING
        if category in (FileCategory.STRIPE_REPORT, FileCategory.RAZORPAY_REPORT, FileCategory.CHARGEBEE_TRANSACTION_EXPORT):
            return FileRole.PAYMENT
        if category in (FileCategory.RAZORPAY_SETTLEMENT, FileCategory.STRIPE_PAYOUT):
            return FileRole.SETTLEMENT
        if category == FileCategory.BANK_STATEMENT:
            return FileRole.BANK
        return FileRole.SOURCE

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
            raise NotFoundError(f"Reconciliation run {run_id} not found")

        if run.status == ReconciliationRunStatus.COMPLETED:
            raise ConflictError(f"Reconciliation run {run_id} is already completed. Create a new run instead.")
        # 1. Update status and clear old results in a separate transaction for visibility
        self.recon_repo.update_run_status(run, ReconciliationRunStatus.IN_PROGRESS)
        self.recon_repo.clear_run_results(run_id, workspace_id)
        self.db.commit()

        # 2. Log start event
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
            if not run_files:
                raise ConflictError("Run has no files attached.")

            # Load all records into a map: role -> [records]
            role_map: dict[str, list[dict]] = {}
            table_map: dict[str, str] = {}
            for rf in run_files:
                recs, table = self._load_canonical_records(workspace_id, rf.uploaded_file_id)
                role_map.setdefault(rf.file_role, []).extend(recs)
                table_map[rf.file_role] = table

            engine = MatchingEngine()
            all_matches = []
            all_exceptions = []
            
            # PHASE 1: BILLING ↔ PAYMENT
            if FileRole.BILLING in role_map and FileRole.PAYMENT in role_map:
                res = engine.run(
                    role_map[FileRole.BILLING], role_map[FileRole.PAYMENT],
                    table_map[FileRole.BILLING], table_map[FileRole.PAYMENT],
                    phase="BILLING_TO_PAYMENT"
                )
                all_matches.extend(res.matches)
                all_exceptions.extend(res.exceptions)

            # PHASE 2: PAYMENT ↔ SETTLEMENT
            if FileRole.PAYMENT in role_map and FileRole.SETTLEMENT in role_map:
                res = engine.run(
                    role_map[FileRole.PAYMENT], role_map[FileRole.SETTLEMENT],
                    table_map[FileRole.PAYMENT], table_map[FileRole.SETTLEMENT],
                    phase="PAYMENT_TO_SETTLEMENT"
                )
                all_matches.extend(res.matches)
                all_exceptions.extend(res.exceptions)

            # PHASE 3: SETTLEMENT ↔ BANK
            if FileRole.SETTLEMENT in role_map and FileRole.BANK in role_map:
                res = engine.run(
                    role_map[FileRole.SETTLEMENT], role_map[FileRole.BANK],
                    table_map[FileRole.SETTLEMENT], table_map[FileRole.BANK],
                    phase="SETTLEMENT_TO_BANK"
                )
                all_matches.extend(res.matches)
                all_exceptions.extend(res.exceptions)
            
            # PHASE 4: PAYMENT ↔ BANK (DIRECT) - Optional fallback
            # (Skip for now unless specifically needed beyond hierarchical batching)
            
            # Post-process to link matching evidence and suppress duplicate exceptions
            all_matches, all_exceptions = self._post_process_hierarchical_results(all_matches, all_exceptions)

            # Clear previous results if re-running (optional, repo.clear_run_results)
            # For now, we assume a fresh run per execution.
            
            # Persist results
            self.recon_repo.bulk_insert_matches(
                workspace_id=workspace_id,
                run_id=run_id,
                matches=all_matches,
                created_by_user_id=user_id,
            )
            self.recon_repo.bulk_insert_exceptions(
                workspace_id=workspace_id,
                run_id=run_id,
                exceptions=all_exceptions,
                created_by_user_id=user_id,
            )
            
            # Metrics & Counters
            total_matches = len(all_matches)
            total_exceptions = len(all_exceptions)
            
            run.total_source_rows = sum(len(role_map.get(r, [])) for r in (FileRole.BILLING, FileRole.PAYMENT, FileRole.SOURCE))
            run.total_target_rows = sum(len(role_map.get(r, [])) for r in (FileRole.BANK, FileRole.SETTLEMENT, FileRole.TARGET))
            run.matched_count = total_matches
            run.exception_count = total_exceptions
            
            # Cash proof rate: matched settlement-bank records / total settlement records
            settlement_recs = role_map.get(FileRole.SETTLEMENT, [])
            if settlement_recs:
                matched_settlement_ids = {m.source_record_id for m in all_matches if m.source_table == table_map[FileRole.SETTLEMENT]}
                run.match_rate_pct = int((len(matched_settlement_ids) / len(settlement_recs)) * 100)
            else:
                run.match_rate_pct = 0 # Default fallback
                
            run.run_date = utcnow()
            run.completed_at = utcnow()
            
            self.recon_repo.update_run_status(run, ReconciliationRunStatus.COMPLETED)

            self.audit_svc.log(
                event_type=AuditEventType.RECONCILIATION_COMPLETED,
                actor_user_id=user_id,
                workspace_id=workspace_id,
                entity_type="reconciliation_run",
                entity_id=run_id,
                metadata={
                    "matched": total_matches,
                    "exceptions": total_exceptions,
                    "match_rate_pct": run.match_rate_pct,
                },
            )
            self.db.commit()

            logger.info(
                "Reconciliation completed",
                run_id=str(run_id),
                matched=total_matches,
                exceptions=total_exceptions,
                match_rate=run.match_rate_pct,
            )
            return run

        except Exception as exc:
            self.db.rollback()
            # Reload run to ensure we can update it after rollback
            run = self.recon_repo.get_run(run_id, workspace_id)
            if run:
                self.recon_repo.update_run_status(
                    run, ReconciliationRunStatus.FAILED, error_message=str(exc)
                )
                self.db.commit()
            logger.error("Reconciliation failed", run_id=str(run_id), error=str(exc))
            raise

    def _post_process_hierarchical_results(
        self, matches: list[Any], exceptions: list[Any]
    ) -> tuple[list[Any], list[Any]]:
        """
        Refines results across layers:
        1. Suppress Payment-level MISSING_BANK_CREDIT if Settlement-level one exists.
        2. (Optional) Propagate Bank UTR/evidence to Payments.
        """
        from app.domain.enums.exception_enums import ExceptionType
        
        # 1. Map: settlement_id -> settlement_record_id
        # We need to find which payments are linked to which settlements via matches
        payment_to_settlement: dict[uuid.UUID, uuid.UUID] = {}
        matched_settlements: set[uuid.UUID] = set()
        
        for m in matches:
            # Payment -> Settlement match
            if m.source_table == "payment_records" and m.target_table == "settlement_records":
                payment_to_settlement[m.source_record_id] = m.target_record_id
            
            # Settlement -> Bank match
            if m.source_table == "settlement_records" and m.target_table == "bank_records":
                matched_settlements.add(m.source_record_id)

        # 2. Identify Settlement-level exceptions
        unmatched_settlement_ids: set[uuid.UUID] = set()
        for ex in exceptions:
            if ex.record_table == "settlement_records" and ex.reason == ExceptionType.MISSING_BANK_CREDIT:
                unmatched_settlement_ids.add(ex.record_id)

        # 3. Filter Exceptions
        filtered_exceptions = []
        for ex in exceptions:
            # Rule: If payment P belongs to settlement S, and S is missing from bank, 
            # we already have a MISSING_BANK_CREDIT for S. 
            # So we remove the individual MISSING_BANK_CREDIT for P to avoid noise.
            if ex.record_table == "payment_records" and ex.reason == ExceptionType.MISSING_BANK_CREDIT:
                parent_sid = payment_to_settlement.get(ex.record_id)
                if parent_sid and parent_sid in unmatched_settlement_ids:
                    # Suppress duplicate noise
                    continue
                
                # Also suppress if parent settlement DID match a bank (propagation of success)
                if parent_sid and parent_sid in matched_settlements:
                    continue
            
            filtered_exceptions.append(ex)
            
        return matches, filtered_exceptions

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
        
    def get_match_evidence(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, match_id: uuid.UUID
    ) -> dict[str, Any]:
        """Fetch the source and target records associated with a match candidate."""
        match = self.recon_repo.get_match(match_id, run_id, workspace_id)
        if not match:
            raise NotFoundError(f"Match {match_id} not found.")
            
        source_rec = self._load_single_record(
            workspace_id, match.source_table, match.source_record_id
        )
        target_rec = self._load_single_record(
            workspace_id, match.target_table, match.target_record_id
        )
        
        return {
            "match_id": str(match_id),
            "source": source_rec,
            "target": target_rec,
            "match_strategy": match.match_strategy,
            "confidence_score": match.confidence_score,
            "amount_delta": float(match.amount_delta) if match.amount_delta else 0,
        }

    def _load_single_record(
        self, workspace_id: uuid.UUID, table_name: str, record_id: uuid.UUID
    ) -> dict[str, Any]:
        """Utility to fetch a record from any canonical table by ID."""
        # Find model by table name
        model_cls = next((m for m in CATEGORY_MODEL_MAP.values() if m.__tablename__ == table_name), None)
        if not model_cls:
             return {"error": f"Table {table_name} not found"}
             
        row = self.db.query(model_cls).filter(
            model_cls.workspace_id == workspace_id,
            model_cls.id == record_id
        ).first()
        
        if not row:
            return {"error": "Record not found"}
            
        return _model_to_dict(row)

    def get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> ReconciliationRun:
        run = self.recon_repo.get_run(run_id, workspace_id)
        if not run:
            raise NotFoundError(f"ReconciliationRun {run_id} not found.")
        
        run.exception_summary = self.recon_repo.get_exception_summary(run_id, workspace_id)
        return run

    def list_runs(
        self, workspace_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReconciliationRun], int]:
        offset = (page - 1) * page_size
        runs, total = self.recon_repo.list_runs(workspace_id, limit=page_size, offset=offset)
        for r in runs:
            r.exception_summary = self.recon_repo.get_exception_summary(r.id, workspace_id)
        return runs, total

    def review_match(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        match_id: uuid.UUID,
        action: str,
        user_id: uuid.UUID,
        note: Optional[str] = None,
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
        note: Optional[str] = None,
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