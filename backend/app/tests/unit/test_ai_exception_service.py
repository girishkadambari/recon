"""
Unit tests: AI exception service helpers — no Anthropic calls, no DB.
Tests the prompt formatting and response validation logic in isolation.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.ai.services.ai_exception_service import explain_exception, generate_run_summary


MOCK_EXPLANATION_RESPONSE = {
    "explanation": "This payment was not matched because the bank statement did not contain a corresponding credit for this amount within the reconciliation window.",
    "probable_cause": "Settlement pending",
    "recommended_action": "Check the bank statement for the following week to see if the credit arrived late.",
    "confidence": "HIGH",
}

MOCK_SUMMARY_RESPONSE = {
    "headline": "Jan 2024 Stripe Recon: 94% match rate with 2 open exceptions",
    "summary": "The January 2024 Stripe reconciliation completed with a 94% match rate. Three payments were matched exactly by transaction ID, and one remains unmatched in the bank statement. Immediate review is recommended for the 2 open exceptions.",
    "risk_level": "LOW",
    "key_findings": [
        "94% match rate — within acceptable range",
        "2 unmatched SOURCE records require review",
        "1 BANK_EXTRA credit has no gateway counterpart",
    ],
    "recommended_actions": [
        "Investigate the 2 unmatched Stripe payments",
        "Check if BANK_EXTRA credit is a refund or transfer",
    ],
    "requires_immediate_attention": False,
}


class TestExplainException:

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_returns_structured_explanation(self, mock_complete):
        mock_complete.return_value = MOCK_EXPLANATION_RESPONSE

        result = explain_exception(
            run_name="Jan 2024 Reconciliation",
            source_category="STRIPE_REPORT",
            target_category="BANK_STATEMENT",
            match_rate_pct=94,
            file_role="SOURCE",
            reason_code="UNMATCHED_SOURCE",
            amount="5000.00",
            currency="INR",
            record_data={"payment_id": "pay_003", "amount": "5000.00"},
        )

        assert result["explanation"] == MOCK_EXPLANATION_RESPONSE["explanation"]
        assert result["probable_cause"] == "Settlement pending"
        assert result["recommended_action"].startswith("Check")
        assert result["confidence"] == "HIGH"

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_invalid_confidence_defaults_to_low(self, mock_complete):
        mock_complete.return_value = {
            **MOCK_EXPLANATION_RESPONSE,
            "confidence": "VERY_HIGH",  # invalid
        }

        result = explain_exception(
            run_name="Test",
            source_category="STRIPE_REPORT",
            target_category="BANK_STATEMENT",
            match_rate_pct=80,
            file_role="SOURCE",
            reason_code="UNMATCHED_SOURCE",
            amount="1000",
            currency="INR",
            record_data={},
        )
        assert result["confidence"] == "LOW"

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_missing_fields_get_defaults(self, mock_complete):
        mock_complete.return_value = {}  # AI returns empty dict

        result = explain_exception(
            run_name="Test",
            source_category="X",
            target_category="Y",
            match_rate_pct=50,
            file_role="TARGET",
            reason_code="UNMATCHED_TARGET",
            amount="500",
            currency="INR",
            record_data={},
        )
        assert result["explanation"] == "Unable to generate explanation."
        assert result["probable_cause"] == "Unknown"
        assert result["confidence"] == "LOW"


class TestGenerateRunSummary:

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_returns_structured_summary(self, mock_complete):
        mock_complete.return_value = MOCK_SUMMARY_RESPONSE

        result = generate_run_summary(
            run_name="Jan 2024 Reconciliation",
            completed_at="2024-01-31T10:00:00Z",
            source_category="STRIPE_REPORT",
            target_category="BANK_STATEMENT",
            total_source_rows=4,
            total_target_rows=4,
            matched_count=3,
            match_rate_pct=94,
            exception_count=2,
            exception_breakdown={"UNMATCHED_SOURCE": 1, "UNMATCHED_TARGET": 1},
            strategy_breakdown={"EXACT_ID": 3},
        )

        assert result["headline"].startswith("Jan 2024")
        assert result["risk_level"] == "LOW"
        assert len(result["key_findings"]) == 3
        assert result["requires_immediate_attention"] is False

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_provides_defaults_on_missing_fields(self, mock_complete):
        mock_complete.return_value = {}

        result = generate_run_summary(
            run_name="Q1 Recon",
            completed_at="2024-03-31",
            source_category="CHARGEBEE_INVOICE_EXPORT",
            target_category="BANK_STATEMENT",
            total_source_rows=100,
            total_target_rows=95,
            matched_count=90,
            match_rate_pct=90,
            exception_count=10,
            exception_breakdown={},
            strategy_breakdown={},
        )

        assert result["headline"] == "Q1 Recon — Reconciliation Complete"
        assert result["risk_level"] == "MEDIUM"
        assert result["key_findings"] == []
        assert result["requires_immediate_attention"] is False
