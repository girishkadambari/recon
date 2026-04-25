"""
Unit tests: normalization helpers.

Tests the pure helper functions _safe_decimal and _safe_datetime
without any database or Anthropic calls.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.domain.services.normalization_service import _safe_decimal, _safe_datetime


class TestSafeDecimal:
    def test_parses_plain_number(self):
        assert _safe_decimal("5000.00") == Decimal("5000.00")

    def test_parses_integer_string(self):
        assert _safe_decimal("12000") == Decimal("12000")

    def test_strips_currency_symbol_inr(self):
        assert _safe_decimal("₹5000.00") == Decimal("5000.00")

    def test_strips_currency_symbol_usd(self):
        assert _safe_decimal("$1,234.56") == Decimal("1234.56")

    def test_strips_thousands_separator(self):
        assert _safe_decimal("1,00,000.00") == Decimal("100000.00")

    def test_returns_none_for_empty(self):
        assert _safe_decimal("") is None

    def test_returns_none_for_na(self):
        assert _safe_decimal("N/A") is None

    def test_returns_none_for_none(self):
        assert _safe_decimal(None) is None

    def test_returns_none_for_text(self):
        assert _safe_decimal("unknown") is None

    def test_negative_number(self):
        assert _safe_decimal("-150.75") == Decimal("-150.75")


class TestSafeDatetime:
    def _utc(self, **kwargs) -> datetime:
        return datetime(tzinfo=timezone.utc, **kwargs)

    def test_parses_iso_format(self):
        dt = _safe_datetime("2024-01-15")
        assert dt is not None
        assert dt.year == 2024 and dt.month == 1 and dt.day == 15

    def test_parses_iso_with_time(self):
        dt = _safe_datetime("2024-01-15T10:30:00")
        assert dt is not None
        assert dt.hour == 10

    def test_parses_iso_utc_z(self):
        dt = _safe_datetime("2024-01-15T10:30:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_parses_dd_mm_yyyy(self):
        dt = _safe_datetime("15/01/2024")
        assert dt is not None
        assert dt.year == 2024

    def test_parses_datetime_with_space(self):
        dt = _safe_datetime("2024-01-15 10:30:45")
        assert dt is not None
        assert dt.hour == 10

    def test_returns_none_for_empty(self):
        assert _safe_datetime("") is None

    def test_returns_none_for_na(self):
        assert _safe_datetime("N/A") is None

    def test_returns_none_for_none(self):
        assert _safe_datetime(None) is None

    def test_always_timezone_aware(self):
        dt = _safe_datetime("2024-01-15")
        assert dt.tzinfo is not None


class TestApplyMapping:
    """Tests the normalization mapping logic without a DB."""

    def test_amount_fields_are_decimal(self):
        from app.domain.services.normalization_service import NormalizationService
        import uuid
        from datetime import timezone

        # We can test _apply_mapping directly without a DB
        svc = NormalizationService.__new__(NormalizationService)

        now = datetime.now(timezone.utc)
        ws_id = uuid.uuid4()
        file_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mapping = {
            "Amount": "gross_amount",
            "Fee": "fee_amount",
            "Date": "transaction_date",
            "PaymentID": "transaction_id",
            "Notes": "ignore",
        }
        raw_row = {
            "Amount": "5000.00",
            "Fee": "150.00",
            "Date": "2024-01-15",
            "PaymentID": "pay_001",
            "Notes": "internal note",
        }

        result = svc._apply_mapping(
            raw_row=raw_row,
            mapping=mapping,
            row_number=1,
            workspace_id=ws_id,
            uploaded_file_id=file_id,
            user_id=user_id,
            now=now,
        )

        assert result["gross_amount"] == Decimal("5000.00")
        assert result["fee_amount"] == Decimal("150.00")
        assert isinstance(result["transaction_date"], datetime)
        assert result["transaction_id"] == "pay_001"
        assert "Notes" not in result  # ignored
        assert "ignore" not in result  # not stored as a key
