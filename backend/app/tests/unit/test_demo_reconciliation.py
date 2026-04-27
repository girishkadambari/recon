import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock
from app.domain.services.matching_engine import MatchingEngine
from app.domain.services.reconciliation_service import ReconciliationService
from app.domain.enums.reconciliation_enums import MatchStatus, MatchStrategy, FileRole, ReconciliationRunStatus
from app.domain.enums.exception_enums import ExceptionType
from app.domain.enums.file_enums import FileCategory, UploadedFileStatus
from app.domain.enums.mapping_enums import NormalizationStatus, MappingStatus

def test_invoice_id_to_order_id_match():
    # Scenario: Billing system has invoice_id, Gateway has order_id
    engine = MatchingEngine()
    invoices = [{"id": uuid.uuid4(), "invoice_id": "INV_A1", "amount": Decimal("5000")}]
    payments = [{"id": uuid.uuid4(), "order_id": "INV_A1", "gross_amount": Decimal("5000")}]
    
    out = engine.run(invoices, payments, "invoices", "payments", phase="BILLING_TO_PAYMENT")
    assert len(out.matches) == 1
    assert out.matches[0].status == MatchStatus.APPROVED

def test_demo_set_s1_matches_bank_hdfc():
    engine = MatchingEngine()
    settlements = [{"id": uuid.uuid4(), "utr": "UTR_HDFC_001", "settlement_amount": Decimal("6823")}]
    bank = [{"id": uuid.uuid4(), "utr": "UTR_HDFC_001", "credit_amount": Decimal("6823")}]
    
    out = engine.run(settlements, bank, "settlements", "bank", phase="SETTLEMENT_TO_BANK")
    assert len(out.matches) == 1
    assert out.matches[0].status == MatchStatus.APPROVED

def test_demo_set_s3_matches_bank_axis_substring():
    engine = MatchingEngine()
    settlements = [{"id": uuid.uuid4(), "utr": "UTR_AXIS_777", "settlement_amount": Decimal("1000")}]
    bank = [{"id": uuid.uuid4(), "narration": "SETTLEMENT FOR UTR_AXIS_777", "credit_amount": Decimal("1000")}]
    
    out = engine.run(settlements, bank, "settlements", "bank", phase="SETTLEMENT_TO_BANK")
    assert len(out.matches) == 1
    assert out.matches[0].match_strategy == MatchStrategy.UTR
    assert out.matches[0].status == MatchStatus.APPROVED

def test_demo_set_s2_creates_missing_bank_credit():
    engine = MatchingEngine()
    settlements = [{"id": uuid.uuid4(), "utr": "UTR_ICICI_999", "settlement_amount": Decimal("2000")}]
    bank = []
    out = engine.run(settlements, bank, "settlements", "bank", phase="SETTLEMENT_TO_BANK")
    assert len(out.exceptions) == 1
    assert out.exceptions[0].reason == ExceptionType.MISSING_BANK_CREDIT

def test_demo_pay_d1_creates_missing_invoice():
    engine = MatchingEngine()
    invoices = []
    payments = [{"id": uuid.uuid4(), "order_id": "order_D1", "gross_amount": Decimal("1200")}]
    out = engine.run(invoices, payments, "invoices", "payments", phase="BILLING_TO_PAYMENT")
    assert out.exceptions[0].reason == ExceptionType.MISSING_INVOICE

def test_demo_inv_z1_creates_missing_payment():
    engine = MatchingEngine()
    invoices = [{"id": uuid.uuid4(), "order_id": "INV_Z1", "amount": Decimal("500")}]
    payments = []
    out = engine.run(invoices, payments, "invoices", "payments", phase="BILLING_TO_PAYMENT")
    assert out.exceptions[0].reason == ExceptionType.MISSING_PAYMENT

def test_demo_neft_creates_offline_candidate():
    engine = MatchingEngine()
    settlements = []
    bank = [{"id": uuid.uuid4(), "narration": "NEFT TRANSFER 882211", "credit_amount": Decimal("1000")}]
    out = engine.run(settlements, bank, "settlements", "bank", phase="SETTLEMENT_TO_BANK")
    assert out.exceptions[0].reason == ExceptionType.OFFLINE_PAYMENT_CANDIDATE

def test_settlement_batch_amount_diff_naming():
    engine = MatchingEngine()
    payments = [{"id": uuid.uuid4(), "settlement_id": "SET_1", "gross_amount": Decimal("1000"), "fee_amount": Decimal("20")}]
    settlements = [{"id": uuid.uuid4(), "settlement_id": "SET_1", "settlement_amount": Decimal("950")}] # Should be 980
    
    out = engine.run(payments, settlements, "payments", "settlements", phase="PAYMENT_TO_SETTLEMENT")
    assert out.exceptions[0].reason == ExceptionType.SETTLEMENT_BATCH_AMOUNT_DIFF

def test_no_missing_bank_credit_propagation():
    # If parent settlement matched bank, don't show individual payment bank exceptions
    from app.domain.services.reconciliation_service import ReconciliationService
    service = ReconciliationService(MagicMock())
    
    p_id = uuid.uuid4()
    s_id = uuid.uuid4()
    b_id = uuid.uuid4()
    
    matches = [
        MagicMock(source_record_id=p_id, target_record_id=s_id, source_table="payment_records", target_table="settlement_records"),
        MagicMock(source_record_id=s_id, target_record_id=b_id, source_table="settlement_records", target_table="bank_records")
    ]
    exceptions = [
        MagicMock(record_id=p_id, record_table="payment_records", reason=ExceptionType.MISSING_BANK_CREDIT)
    ]
    
    _, filtered = service._post_process_hierarchical_results(matches, exceptions)
    assert len(filtered) == 0

def test_amount_only_is_pending_review():
    engine = MatchingEngine()
    src = [{"id": uuid.uuid4(), "amount": Decimal("1000")}]
    tgt = [{"id": uuid.uuid4(), "amount": Decimal("1000")}]
    out = engine.run(src, tgt, "billing", "payment", phase="BILLING_TO_PAYMENT")
    assert out.matches[0].status == MatchStatus.PENDING_REVIEW

def test_settlement_amount_helper_priority():
    from app.domain.services.matching_engine import _settlement_amount
    rec = {
        "gross_amount": Decimal("1000"),
        "net_amount": Decimal("980"),
        "settlement_amount": Decimal("975")
    }
    # Should prefer settlement_amount
    assert _settlement_amount(rec) == Decimal("975")
