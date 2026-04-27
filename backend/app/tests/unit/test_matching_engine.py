"""
Unit tests: MatchingEngine — pure logic, no DB, no AI.
"""
from __future__ import annotations
from typing import Optional
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta

import pytest

from app.domain.services.matching_engine import MatchingEngine, EngineOutput
from app.domain.enums.exception_enums import ExceptionType
from app.domain.enums.reconciliation_enums import (
    FileRole,
    MatchStatus,
    MatchStrategy,
)


def _make_payment(
    transaction_id: Optional[str] = None,
    amount: Decimal = Decimal("1000.00"),
    date: Optional[datetime] = None,
    utr: Optional[str] = None,
    currency: str = "INR",
) -> dict:
    return {
        "id": uuid.uuid4(),
        "transaction_id": transaction_id,
        "gross_amount": amount,
        "currency": currency,
        "transaction_date": date,
        "utr": utr,
    }


def _make_bank(
    utr: Optional[str] = None,
    amount: Decimal = Decimal("1000.00"),
    date: Optional[datetime] = None,
    reference: Optional[str] = None,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "utr": utr,
        "reference": reference,
        "credit_amount": amount,
        "transaction_date": date,
    }


BASE_DATE = datetime(2024, 1, 15, tzinfo=timezone.utc)


class TestExactIDMatch:
    def test_matches_by_transaction_id(self):
        src = [_make_payment(transaction_id="TXN001", amount=Decimal("5000"))]
        tgt = [_make_bank(utr="TXN001", amount=Decimal("5000"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        assert out.matches[0].confidence_score == 100
        assert out.matches[0].match_strategy == MatchStrategy.EXACT_ID
        assert out.matches[0].status == MatchStatus.APPROVED
        assert len(out.exceptions) == 0

    def test_matches_by_utr_field(self):
        src = [_make_payment(utr="UTR12345", amount=Decimal("2500"))]
        tgt = [_make_bank(utr="UTR12345", amount=Decimal("2500"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        # UTR logic now uses UTR strategy if 'utr' string is in the value
        assert out.matches[0].match_strategy in (MatchStrategy.EXACT_ID, MatchStrategy.UTR)

    def test_id_match_case_insensitive(self):
        src = [_make_payment(transaction_id="TXN-ABC")]
        tgt = [_make_bank(utr="txn-abc", amount=Decimal("1000"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1


class TestAmountDateMatch:
    def test_matches_by_amount_and_date(self):
        src = [_make_payment(amount=Decimal("3500.00"), date=BASE_DATE)]
        tgt = [_make_bank(amount=Decimal("3500.00"), date=BASE_DATE + timedelta(days=2))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        assert out.matches[0].match_strategy == MatchStrategy.AMOUNT_DATE
        assert out.matches[0].confidence_score == 92

    def test_date_too_far_falls_to_amount_only(self):
        src = [_make_payment(amount=Decimal("3500.00"), date=BASE_DATE)]
        tgt = [_make_bank(amount=Decimal("3500.00"), date=BASE_DATE + timedelta(days=10))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        # Falls through to AMOUNT_ONLY (Strategy 3) instead of NET_SETTLEMENT
        assert out.matches[0].match_strategy == MatchStrategy.AMOUNT_ONLY


class TestAmountOnlyMatch:
    def test_matches_by_amount_only_when_date_beyond_window(self):
        """
        AMOUNT_ONLY is reached when exact-amount candidates exist but none
        pass the date-window check (date delta > SETTLEMENT_DATE_WINDOW_DAYS).
        Records with no date at all fall into AMOUNT_DATE (null-date branch).
        """
        from datetime import timedelta
        from app.core.constants import SETTLEMENT_DATE_WINDOW_DAYS
        far_date = BASE_DATE + timedelta(days=SETTLEMENT_DATE_WINDOW_DAYS + 1)
        src = [_make_payment(amount=Decimal("7890.50"), date=BASE_DATE)]
        tgt = [_make_bank(amount=Decimal("7890.50"), date=far_date)]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        # Falls through to AMOUNT_ONLY since date window is exceeded
        assert out.matches[0].match_strategy == MatchStrategy.AMOUNT_ONLY
        assert out.matches[0].status == MatchStatus.MATCHED


class TestFuzzyAmountMatch:
    def test_fuzzy_within_tolerance(self):
        # 5% tolerance on 10000 = 500
        src = [_make_payment(amount=Decimal("10000.00"))]
        tgt = [_make_bank(amount=Decimal("10400.00"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 1
        assert out.matches[0].match_strategy == MatchStrategy.FUZZY_AMOUNT
        assert out.matches[0].confidence_score == 62

    def test_beyond_tolerance_is_exception(self):
        src = [_make_payment(amount=Decimal("10000.00"))]
        tgt = [_make_bank(amount=Decimal("20000.00"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.matches) == 0
        assert len(out.exceptions) == 2


class TestExceptions:
    def test_unmatched_source_creates_exception(self):
        src = [_make_payment(transaction_id="UNIQ001", amount=Decimal("9999"))]
        tgt = []
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.exceptions) == 1
        # Payment unmatched for Bank Target -> MISSING_BANK_CREDIT
        assert out.exceptions[0].reason == ExceptionType.MISSING_BANK_CREDIT
        assert out.exceptions[0].file_role == FileRole.SOURCE

    def test_unmatched_target_creates_exception(self):
        src = []
        tgt = [_make_bank(utr="BANKONLY", amount=Decimal("500"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.exceptions) == 1
        assert out.exceptions[0].reason == ExceptionType.UNKNOWN_BANK_CREDIT
        assert out.exceptions[0].file_role == FileRole.TARGET

    def test_both_unmatched_two_exceptions(self):
        src = [_make_payment(transaction_id="S1", amount=Decimal("1111"))]
        tgt = [_make_bank(utr="T1", amount=Decimal("9999"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert len(out.exceptions) == 2


class TestRecordNotReused:
    def test_matched_target_not_reused(self):
        """One target row cannot be matched to multiple sources."""
        tgt_row = _make_bank(utr="SHARED", amount=Decimal("5000"))
        src = [
            _make_payment(transaction_id="SHARED", amount=Decimal("5000")),
            _make_payment(transaction_id="SHARED", amount=Decimal("5000")),
        ]
        engine = MatchingEngine()
        out = engine.run(src, [tgt_row], "payment_records", "bank_records")
        # Only one can be matched
        assert len(out.matches) == 1
        assert len(out.exceptions) >= 1


class TestMatchRate:
    def test_perfect_match_rate_100(self):
        pairs = [
            ("TXN%03d" % i, Decimal("1000"))
            for i in range(10)
        ]
        src = [_make_payment(transaction_id=t, amount=a) for t, a in pairs]
        tgt = [_make_bank(utr=t, amount=a) for t, a in pairs]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert out.matched_count == 10
        assert out.exception_count == 0
        assert out.match_rate_pct == 100

    def test_zero_matches_rate_0(self):
        src = [_make_payment(amount=Decimal("111"))]
        tgt = [_make_bank(amount=Decimal("999"))]
        engine = MatchingEngine()
        out = engine.run(src, tgt, "payment_records", "bank_records")
        assert out.match_rate_pct == 0

    def test_empty_inputs(self):
        engine = MatchingEngine()
        out = engine.run([], [], "payment_records", "bank_records")
        assert out.matched_count == 0
        assert out.exception_count == 0