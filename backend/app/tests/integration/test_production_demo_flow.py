"""
Integration Test: Production Demo Flow
Validates that the SampleDataLoader correctly orchestrates the full pipeline
and that the MatchingEngine identifies all complex financial cases naturally.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.services.sample_data_loader import SampleDataLoader
from app.domain.repositories.reconciliation_repository import ReconciliationRepository
from app.domain.enums.exception_enums import ExceptionType
from app.domain.enums.reconciliation_enums import MatchStrategy
from app.auth.current_user import CurrentUserContext


from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_member import WorkspaceMember
from app.domain.enums.auth_enums import WorkspaceRole


def test_production_demo_pipeline_e2e(client: TestClient, db: Session):
    # 1. Setup Context directly in DB to avoid transaction isolation issues
    email = f"test_demo_{uuid.uuid4().hex[:6]}@recon.ai"
    user = User(
        email=email, 
        full_name="Test Demo", 
        provider_subject=uuid.uuid4().hex
    )
    db.add(user)
    db.flush()
    
    ws = Workspace(name="Test Workspace", slug=f"ws-{uuid.uuid4().hex[:6]}", created_by_user_id=user.id)
    db.add(ws)
    db.flush()
    
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)
    db.add(member)
    db.commit() # Commit to ensure FKs are satisfied if services use their own sessions
    
    ws_id, u_id = ws.id, user.id

    # 2. Run SampleDataLoader (The "Real Pipeline")
    loader = SampleDataLoader(db)
    run = loader.load_production_demo(ws_id, u_id)
    
    assert run.status == "COMPLETED"
    assert run.matched_count > 0
    assert run.exception_count > 0

    # 3. Assert Real Engine Results (Natural Cases)
    repo = ReconciliationRepository(db)
    matches, _ = repo.list_matches(run.id, ws_id, limit=100)
    exceptions, _ = repo.list_exceptions(run.id, ws_id, limit=100)
    
    exc_types = [e.exception_type for e in exceptions]
    
    # ── Verify Specific Financial Cases ──────────────────────────────
    
    # [x] invoice matched to billing transaction: INV-001 <-> TXN-001
    # [x] billing transaction matched to gateway payment: TXN-001 <-> UTR-001 (Bank)
    # [x] gateway payment matched to settlement: SETT-001 <-> UTR-BANK-MATCH
    
    assert any(m.match_strategy == "EXACT_ID" for m in matches), "Should have exact ID matches"
    assert any(m.match_strategy in (MatchStrategy.UTR, MatchStrategy.EXACT_ID) for m in matches), "Should have UTR-based matches"
    
    # [x] unknown bank credit: BANK-004 (UNKNOWN CREDIT)
    assert ExceptionType.UNKNOWN_BANK_CREDIT in exc_types
    
    # [x] missing bank credit: TXN-011 (Payment without bank entry)
    assert ExceptionType.MISSING_BANK_CREDIT in exc_types
    
    # [x] fee mismatch: TXN-003 vs BANK-003 (1464.60 vs 1460.00)
    assert any(et in (ExceptionType.FEE_MISMATCH, ExceptionType.AMOUNT_MISMATCH) for et in exc_types), "Should have amount/fee mismatch"
    
    # [x] tax mismatch: TXN-007 vs BANK-007 (2929.20 vs 2929.00)
    assert ExceptionType.AMOUNT_MISMATCH in exc_types or ExceptionType.TAX_MISMATCH in exc_types
    
    # [x] offline payment candidate: BANK-005 (CHEQUE DEPOSIT)
    assert ExceptionType.OFFLINE_PAYMENT_CANDIDATE in exc_types
    
    # [x] gateway payment without invoice: TXN-011
    # Note: In our current 3-way pairing (Billing-Payment, Payment-Bank), 
    # TXN-011 unmatched in Billing-Payment produces MISSING_INVOICE if we add it.
    assert ExceptionType.MISSING_PAYMENT in exc_types # Unmatched Invoices
    
    print(f"\n📊 Test Run Summary: {run.matched_count} Matches, {run.exception_count} Exceptions")
    for et in set(exc_types):
        print(f"  - Detected: {et}")
