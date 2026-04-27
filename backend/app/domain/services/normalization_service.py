"""
NormalizationService — transforms source records into canonical records.

Business logic:
  1. Load the confirmed ColumnMapping for the file
  2. Stream through all SourceRecords for that file
  3. For each row: apply the mapping, parse Decimal amounts, parse dates
  4. Bulk insert into the appropriate canonical table
  5. Mark ColumnMapping.normalization_status = COMPLETED
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.money import parse_decimal
from app.domain.enums.audit_enums import AuditEventType
from app.domain.enums.file_enums import FileCategory, UploadedFileStatus
from app.domain.enums.mapping_enums import MappingStatus, NormalizationStatus, CanonicalField
from app.domain.models.canonical_records import (
    BankRecord,
    BillingTransactionRecord,
    InvoiceRecord,
    PaymentRecord,
    SettlementRecord,
)
from app.domain.repositories.column_mapping_repository import ColumnMappingRepository
from app.domain.repositories.source_record_repository import SourceRecordRepository
from app.domain.repositories.uploaded_file_repository import UploadedFileRepository
from app.domain.services.audit_service import AuditService
from app.core.constants import DEFAULT_CURRENCY

logger = structlog.get_logger(__name__)

# How many source records to process per DB flush (avoids huge in-memory lists)
BATCH_SIZE = 500

# Amount fields that need Decimal parsing
AMOUNT_FIELDS = {
    CanonicalField.GROSS_AMOUNT,
    CanonicalField.NET_AMOUNT,
    CanonicalField.FEE_AMOUNT,
    CanonicalField.TAX_AMOUNT,
    CanonicalField.REFUND_AMOUNT,
    CanonicalField.CREDIT_AMOUNT,
    CanonicalField.DEBIT_AMOUNT,
    CanonicalField.BALANCE,
}

# Date fields that need datetime parsing
DATE_FIELDS = {
    CanonicalField.TRANSACTION_DATE,
    CanonicalField.SETTLEMENT_DATE,
    CanonicalField.INVOICE_DATE,
    CanonicalField.DUE_DATE,
}

# file_category → canonical model + its amount/identity fields
CATEGORY_MODEL_MAP = {
    FileCategory.STRIPE_REPORT: PaymentRecord,
    FileCategory.RAZORPAY_REPORT: PaymentRecord,
    FileCategory.CHARGEBEE_INVOICE_EXPORT: BillingTransactionRecord,
    FileCategory.CHARGEBEE_TRANSACTION_EXPORT: BillingTransactionRecord,
    FileCategory.BANK_STATEMENT: BankRecord,
    FileCategory.INVOICE_EXPORT: InvoiceRecord,
    FileCategory.RAZORPAY_SETTLEMENT: SettlementRecord,
    FileCategory.STRIPE_PAYOUT: SettlementRecord,
}


class NormalizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.mapping_repo = ColumnMappingRepository(db)
        self.source_repo = SourceRecordRepository(db)
        self.file_repo = UploadedFileRepository(db)
        self.audit_svc = AuditService(db)

    def normalize_file(
        self,
        workspace_id: uuid.UUID,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Run normalization for a confirmed ColumnMapping.
        Returns {"canonical_table": str, "rows_inserted": int}.
        """
        # ── Validate ──────────────────────────────────────────────────
        col_mapping = self.mapping_repo.get_by_file_id(file_id, workspace_id)
        if not col_mapping:
            raise NotFoundError(
                f"No column mapping found for file {file_id}. Suggest and confirm one first."
            )
        if col_mapping.status != MappingStatus.CONFIRMED:
            raise ConflictError(
                f"Column mapping for file {file_id} is not confirmed. "
                "Confirm the mapping before running normalization."
            )
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"File {file_id} not found.")

        model_cls = CATEGORY_MODEL_MAP.get(uf.file_category)
        if not model_cls:
            raise ConflictError(
                f"Unknown file_category '{uf.file_category}' — cannot determine canonical table."
            )

        # Block concurrent runs — already in progress
        if col_mapping.normalization_status == NormalizationStatus.IN_PROGRESS:
            raise ConflictError(
                f"Normalization for file {file_id} is already in progress. "
                "Wait for it to complete before re-running."
            )

        mapping: dict[str, str] = col_mapping.mapping_json
        from app.core.dates import utcnow
        now = utcnow()
        rows_inserted = 0

        try:
            # Always delete any existing canonical rows first to avoid duplicates
            logger.info(
                "Clearing existing canonical rows before normalization",
                file_id=str(file_id),
                previous_status=col_mapping.normalization_status,
            )
            deleted = self.db.query(model_cls).filter(
                model_cls.workspace_id == workspace_id,
                model_cls.uploaded_file_id == file_id,
            ).delete(synchronize_session=False)
            if deleted > 0:
                logger.info("Deleted existing canonical rows", count=deleted)
            self.db.flush()

            # ── Mark file + mapping as IN_PROGRESS ─────────────────────────
            self.mapping_repo.update_normalization_status(
                col_mapping, NormalizationStatus.IN_PROGRESS
            )
            self.file_repo.update_status(uf, UploadedFileStatus.NORMALIZING)
            self.db.flush()
            # Process in batches of BATCH_SIZE
            offset = 0
            while True:
                records = self.source_repo.list_for_file(
                    workspace_id=workspace_id,
                    uploaded_file_id=file_id,
                    limit=BATCH_SIZE,
                    offset=offset,
                )
                if not records:
                    break

                batch = []
                for record in records:
                    canonical = self._apply_mapping(
                        raw_row=record.raw_data_json,
                        mapping=mapping,
                        row_number=record.row_number,
                        workspace_id=workspace_id,
                        uploaded_file_id=file_id,
                        user_id=user_id,
                        now=now,
                    )
                    batch.append(canonical)

                self.db.bulk_insert_mappings(model_cls, batch)
                self.db.flush()
                rows_inserted += len(batch)
                offset += BATCH_SIZE

            # ── COMPLETED ──────────────────────────────────────────────
            self.mapping_repo.update_normalization_status(
                col_mapping, NormalizationStatus.COMPLETED
            )
            self.file_repo.update_status(uf, UploadedFileStatus.NORMALIZED)
            self.audit_svc.log(
                event_type=AuditEventType.NORMALIZATION_COMPLETED,
                actor_user_id=user_id,
                workspace_id=workspace_id,
                entity_type="column_mapping",
                entity_id=col_mapping.id,
                metadata={
                    "file_id": str(file_id),
                    "canonical_table": model_cls.__tablename__,
                    "rows_inserted": rows_inserted,
                },
            )
            self.db.commit()

            logger.info(
                "Normalization complete",
                file_id=str(file_id),
                table=model_cls.__tablename__,
                rows=rows_inserted,
            )
            return {
                "canonical_table": model_cls.__tablename__,
                "rows_inserted": rows_inserted,
                "normalization_status": NormalizationStatus.COMPLETED,
            }

        except Exception as exc:
            self.db.rollback()
            # Reload column mapping and uploaded file to update after rollback
            col_mapping = self.mapping_repo.get_by_file_id(file_id, workspace_id)
            uf = self.file_repo.get_by_id(file_id, workspace_id)
            
            if col_mapping:
                self.mapping_repo.update_normalization_status(
                    col_mapping,
                    NormalizationStatus.FAILED,
                    error=str(exc),
                )
            if uf:
                self.file_repo.update_status(uf, UploadedFileStatus.NORMALIZE_FAILED)
            
            self.db.commit()
            logger.error("Normalization failed", file_id=str(file_id), error=str(exc))
            raise

    def _apply_mapping(
        self,
        raw_row: dict[str, Any],
        mapping: dict[str, str],
        row_number: int,
        workspace_id: uuid.UUID,
        uploaded_file_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
    ) -> dict[str, Any]:
        """
        Apply the column mapping to a single raw row.
        Returns a dict suitable for bulk_insert_mappings.
        """
        import uuid as uuid_lib

        canonical: dict[str, Any] = {
            "id": uuid_lib.uuid4(),
            "workspace_id": workspace_id,
            "uploaded_file_id": uploaded_file_id,
            "row_number": row_number,
            "currency": DEFAULT_CURRENCY,
            "created_at": now,
            "updated_at": now,
            "created_by_user_id": user_id,
            "updated_by_user_id": user_id,
        }

        for raw_col, canonical_field_str in mapping.items():
            try:
                cf = CanonicalField(canonical_field_str)
            except ValueError:
                continue
                
            if cf == CanonicalField.IGNORE:
                continue
                
            raw_val = raw_row.get(raw_col)
            if raw_val is None or raw_val == "":
                continue

            if cf in AMOUNT_FIELDS:
                canonical[cf.value] = _safe_decimal(raw_val)
            elif cf in DATE_FIELDS:
                canonical[cf.value] = _safe_datetime(raw_val)
            else:
                canonical[cf.value] = str(raw_val).strip()

        return canonical

    def get_canonical_rows(
        self,
        workspace_id: uuid.UUID,
        file_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Any], str]:
        """Returns (rows, canonical_table_name) for an already-normalized file."""
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"File {file_id} not found.")
        model_cls = CATEGORY_MODEL_MAP.get(uf.file_category)
        if not model_cls:
            raise NotFoundError(f"No canonical table for category '{uf.file_category}'.")

        rows = (
            self.db.query(model_cls)
            .filter(
                model_cls.workspace_id == workspace_id,
                model_cls.uploaded_file_id == file_id,
            )
            .order_by(model_cls.row_number)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return rows, model_cls.__tablename__


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_decimal(value: Any) -> Optional[Decimal]:
    """Parse any string/number to Decimal. Returns None on failure."""
    if value is None:
        return None
    try:
        # Remove thousands separators and currency symbols
        clean = str(value).replace(",", "").replace("₹", "").replace("$", "").strip()
        if not clean or clean in ("-", "N/A", "n/a", "NA"):
            return None
        return Decimal(clean)
    except (InvalidOperation, ValueError):
        logger.warning("Could not parse decimal", value=str(value)[:50])
        return None


DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d-%b-%Y",
    "%b %d, %Y",
]


def _safe_datetime(value: Any) -> Optional[datetime]:
    """Parse a date/time string to a timezone-aware datetime. Returns None on failure."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw in ("N/A", "n/a", "NA", "None"):
        return None

    # Already timezone-aware ISO format
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    logger.warning("Could not parse date", value=raw[:50])
    return None