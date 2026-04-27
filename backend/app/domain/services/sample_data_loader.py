"""
SampleDataLoader — Production utility to load and reconcile sample data 
using the exact same service pipeline as real customer data.
"""
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

from app.domain.services.file_ingestion_service import FileIngestionService
from app.domain.services.column_mapping_service import ColumnMappingService
from app.domain.services.normalization_service import NormalizationService
from app.domain.services.reconciliation_service import ReconciliationService
from app.domain.services.exception_explanation_service import ExceptionExplanationService

# Pre-defined mappings for our standard sample files
BILLING_MAPPING = {
    "invoice_id": "invoice_id",
    "amount": "gross_amount",
    "currency": "currency",
    "customer": "description",
    "invoice_date": "transaction_date",
    "status": "status"
}

GATEWAY_MAPPING = {
    "txn_id": "transaction_id",
    "invoice_id": "invoice_id",
    "gross_amount": "gross_amount",
    "fee": "fee_amount",
    "tax": "tax_amount",
    "net_amount": "net_amount",
    "currency": "currency",
    "utr": "utr",
    "created_at": "transaction_date"
}

BANK_MAPPING = {
    "date": "transaction_date",
    "narration": "narration",
    "utr": "utr",
    "credit": "credit_amount",
    "debit": "debit_amount",
    "reference": "reference"
}


from app.domain.repositories.column_mapping_repository import ColumnMappingRepository


class SampleDataLoader:
    def __init__(self, db: Session):
        self.db = db
        self.ingestion_svc = FileIngestionService(db)
        self.mapping_repo = ColumnMappingRepository(db)
        self.mapping_svc = ColumnMappingService(db)
        self.norm_svc = NormalizationService(db)
        self.recon_svc = ReconciliationService(db)
        self.ai_svc = ExceptionExplanationService(db)

    def load_production_demo(self, workspace_id: uuid.UUID, user_id: uuid.UUID):
        """
        Runs the full pipeline for the production demo samples:
        billing.csv, gateway_report.csv, bank_statement.csv
        """
        # recon/backend/app/domain/services/sample_data_loader.py -> parents[4] is the recon root
        samples_dir = Path(__file__).resolve().parents[4] / "samples" / "production_demo"
        
        # 1. Ingest
        billing_id = self._ingest(samples_dir / "billing.csv", "INVOICE_EXPORT", workspace_id, user_id)
        gateway_id = self._ingest(samples_dir / "gateway_report.csv", "STRIPE_REPORT", workspace_id, user_id)
        bank_id = self._ingest(samples_dir / "bank_statement.csv", "BANK_STATEMENT", workspace_id, user_id)

        # 2. Map & Normalize
        self._map_and_normalize(billing_id, BILLING_MAPPING, workspace_id, user_id)
        self._map_and_normalize(gateway_id, GATEWAY_MAPPING, workspace_id, user_id)
        self._map_and_normalize(bank_id, BANK_MAPPING, workspace_id, user_id)

        # 3. Reconcile
        run = self.recon_svc.create_run_multi(
            workspace_id=workspace_id,
            user_id=user_id,
            name="Production Demo Recon",
            uploaded_file_ids=[billing_id, gateway_id, bank_id]
        )
        
        completed_run = self.recon_svc.execute_run(
            workspace_id=workspace_id,
            run_id=run.id,
            user_id=user_id
        )

        return completed_run

    def _ingest(self, path: Path, category: str, ws_id: uuid.UUID, u_id: uuid.UUID):
        with open(path, "rb") as f:
            content = f.read()
        return self.ingestion_svc.ingest_file(
            workspace_id=ws_id,
            user_id=u_id,
            file_name=path.name,
            file_bytes=content,
            file_category=category,
            mime_type="text/csv"
        ).id

    def _map_and_normalize(self, file_id: uuid.UUID, mapping: dict, ws_id: uuid.UUID, u_id: uuid.UUID):
        # Initialize mapping record in DB first
        self.mapping_repo.create_or_update(
            workspace_id=ws_id,
            uploaded_file_id=file_id,
            mapping_json=mapping,
            ai_suggested_mapping_json=mapping,
            ai_confidence_score=99,
            created_by_user_id=u_id,
        )
        
        # Confirm mapping
        self.mapping_svc.confirm_mapping(
            workspace_id=ws_id,
            file_id=file_id,
            user_id=u_id,
            updated_mapping=mapping,
        )
        # Normalize
        self.norm_svc.normalize_file(
            workspace_id=ws_id,
            file_id=file_id,
            user_id=u_id
        )
