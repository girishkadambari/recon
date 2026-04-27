"""
Integration tests: Phase 5 — AI exception explanations and run summary.

AI calls are mocked — no ANTHROPIC_API_KEY needed.
"""
import io
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Re-use sample data from Phase 4 test
STRIPE_CSV = b"""payment_id,amount,currency,status,created_at
pay_001,5000.00,INR,succeeded,2024-01-15
pay_002,12000.00,INR,succeeded,2024-01-16
pay_003,3500.00,INR,failed,2024-01-17
"""

BANK_CSV = b"""utr,credit_amount,currency,narration,transaction_date
pay_001,5000.00,INR,STRIPE SETTLEMENT,2024-01-15
pay_002,12000.00,INR,STRIPE SETTLEMENT,2024-01-16
BANK_EXTRA,999.00,INR,MISC CREDIT,2024-01-19
"""

MOCK_STRIPE_MAPPING = {
    "mapping": {
        "payment_id": "transaction_id", "amount": "gross_amount",
        "currency": "currency", "status": "status", "created_at": "transaction_date",
    },
    "confidence_score": 95, "notes": "",
}
MOCK_BANK_MAPPING = {
    "mapping": {
        "utr": "utr", "credit_amount": "credit_amount",
        "currency": "currency", "narration": "narration", "transaction_date": "transaction_date",
    },
    "confidence_score": 90, "notes": "",
}

MOCK_AI_EXPLANATION = {
    "explanation": "This payment record did not find a matching bank credit within the reconciliation window.",
    "probable_cause": "Settlement pending",
    "recommended_action": "Check the bank statement for the following business day.",
    "confidence": "HIGH",
}

MOCK_AI_SUMMARY = {
    "headline": "Jan 2024 Stripe: 80% match with 2 exceptions",
    "summary": "The run completed with 2 open exceptions. Review recommended.",
    "risk_level": "MEDIUM",
    "key_findings": ["2 exceptions need review"],
    "recommended_actions": ["Review unmatched records"],
    "requires_immediate_attention": False,
}


def _login(client, email):
    resp = client.post("/api/auth/dev-login", json={"email": email})
    d = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {d['access_token']}"}, "workspace_id": d["workspace_id"]}


def _full_pipeline(client, user, csv_bytes, category, mock_return):
    with patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping", return_value=mock_return):
        resp = client.post(
            "/api/uploads",
            data={"file_category": category},
            files={"file": ("f.csv", io.BytesIO(csv_bytes), "text/csv")},
            headers=user["headers"],
        )
        assert resp.status_code == 201
        file_id = resp.json()["data"]["id"]
        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        resp = client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])
        assert resp.status_code == 200
    return file_id


def _run_reconciliation(client, user):
    """Set up and execute a full reconciliation run. Returns run_id."""
    src_id = _full_pipeline(client, user, STRIPE_CSV, "STRIPE_REPORT", MOCK_STRIPE_MAPPING)
    tgt_id = _full_pipeline(client, user, BANK_CSV, "BANK_STATEMENT", MOCK_BANK_MAPPING)
    resp = client.post(
        "/api/reconciliation-runs",
        json={"name": f"Recon {uuid.uuid4().hex[:4]}", "uploaded_file_ids": [src_id, tgt_id]},
        headers=user["headers"],
    )
    assert resp.status_code == 201
    run_id = resp.json()["data"]["id"]
    resp = client.post(f"/api/reconciliation-runs/{run_id}/run", headers=user["headers"])
    assert resp.status_code == 200
    return run_id


class TestExceptionExplanations:

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_explain_single_exception(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_EXPLANATION
        user = _login(client, f"explain1_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        # Get first open exception
        resp = client.get(f"/api/reconciliation-runs/{run_id}/exceptions", headers=user["headers"])
        exceptions = resp.json()["data"]
        assert len(exceptions) >= 1
        exc_id = exceptions[0]["id"]

        # Explain it
        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/explain",
            headers=user["headers"],
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "explanation" in data
        assert data["explanation"] == MOCK_AI_EXPLANATION["explanation"]
        assert data["probable_cause"] == "Settlement pending"
        assert data["confidence"] == "HIGH"
        assert data["cached"] is False

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_second_call_returns_cached(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_EXPLANATION
        user = _login(client, f"explain2_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.get(f"/api/reconciliation-runs/{run_id}/exceptions", headers=user["headers"])
        exc_id = resp.json()["data"][0]["id"]

        # First call — generates
        client.post(f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/explain", headers=user["headers"])
        # Second call — should use cache (no new AI call)
        mock_ai.reset_mock()
        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/explain",
            headers=user["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["cached"] is True
        mock_ai.assert_not_called()

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_force_refresh_regenerates(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_EXPLANATION
        user = _login(client, f"explain3_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.get(f"/api/reconciliation-runs/{run_id}/exceptions", headers=user["headers"])
        exc_id = resp.json()["data"][0]["id"]

        client.post(f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/explain", headers=user["headers"])
        mock_ai.reset_mock()

        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/explain?force_refresh=true",
            headers=user["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["cached"] is False
        mock_ai.assert_called_once()

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_batch_explain_all_open(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_EXPLANATION
        user = _login(client, f"batch_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.post(f"/api/reconciliation-runs/{run_id}/explain-all", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["explained"] >= 1
        assert data["skipped"] == 0

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_batch_explain_skips_already_explained(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_EXPLANATION
        user = _login(client, f"batch2_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        # First batch
        client.post(f"/api/reconciliation-runs/{run_id}/explain-all", headers=user["headers"])
        mock_ai.reset_mock()

        # Second batch — all should be skipped
        resp = client.post(f"/api/reconciliation-runs/{run_id}/explain-all", headers=user["headers"])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["explained"] == 0
        mock_ai.assert_not_called()

    @patch("app.ai.services.ai_exception_service.complete_json")
    def test_run_summary(self, mock_ai, client: TestClient):
        mock_ai.return_value = MOCK_AI_SUMMARY
        user = _login(client, f"summary_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.get(f"/api/reconciliation-runs/{run_id}/summary", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["run_id"] == run_id
        assert data["headline"] == MOCK_AI_SUMMARY["headline"]
        assert data["risk_level"] == "MEDIUM"
        assert isinstance(data["key_findings"], list)
        assert isinstance(data["recommended_actions"], list)

    def test_explain_pending_run_returns_409(self, client: TestClient):
        user = _login(client, f"pending_{uuid.uuid4().hex[:6]}@x.com")
        # Create run but don't execute — status = PENDING
        src_id = _full_pipeline(client, user, STRIPE_CSV, "STRIPE_REPORT", MOCK_STRIPE_MAPPING)
        tgt_id = _full_pipeline(client, user, BANK_CSV, "BANK_STATEMENT", MOCK_BANK_MAPPING)

        resp = client.post(
            "/api/reconciliation-runs",
            json={"name": f"Pending Run", "uploaded_file_ids": [src_id, tgt_id]},
            headers=user["headers"],
        )
        run_id = resp.json()["data"]["id"]

        resp = client.post(f"/api/reconciliation-runs/{run_id}/explain-all", headers=user["headers"])
        assert resp.status_code == 409

    def test_explain_without_auth_returns_401(self, client: TestClient):
        resp = client.post(
            f"/api/reconciliation-runs/{uuid.uuid4()}/exceptions/{uuid.uuid4()}/explain"
        )
        assert resp.status_code == 401

    def test_explain_nonexistent_exception_returns_404(self, client: TestClient):
        user = _login(client, f"404exc_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/exceptions/{uuid.uuid4()}/explain",
            headers=user["headers"],
        )
        assert resp.status_code == 404
