"""
Integration tests: column mapping + normalization pipeline.

Tests:
  1. Column mapping endpoints (suggest with mocked AI, get, confirm, normalize, rows)
  2. Workspace isolation on all mapping endpoints
  3. Normalization actually inserts canonical rows
  4. Conflict guard: re-normalizing a completed file raises 409

The AI call is mocked — these tests do not need ANTHROPIC_API_KEY.
"""
import io
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

SAMPLE_CSV = b"""payment_id,amount,currency,status,created_at,email
pay_001,5000.00,INR,succeeded,2024-01-15,alice@acme.com
pay_002,12000.00,INR,succeeded,2024-01-16,bob@acme.com
pay_003,3500.00,INR,failed,2024-01-17,charlie@acme.com
"""

# What the AI "returns" (mocked)
MOCK_AI_SUGGESTION = {
    "mapping": {
        "payment_id": "transaction_id",
        "amount": "gross_amount",
        "currency": "currency",
        "status": "status",
        "created_at": "transaction_date",
        "email": "customer_email",
    },
    "confidence_score": 95,
    "notes": "All columns clearly mapped.",
}


def _login(client, email):
    resp = client.post("/api/auth/dev-login", json={"email": email})
    d = resp.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {d['access_token']}"},
        "workspace_id": d["workspace_id"],
    }


def _upload(client, headers, category="STRIPE_REPORT"):
    resp = client.post(
        "/api/uploads",
        data={"file_category": category},
        files={"file": ("stripe.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


class TestColumnMappingFlow:

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_suggest_returns_pending_mapping(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"mapping1_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        resp = client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "PENDING_REVIEW"
        assert data["ai_confidence_score"] == 95
        assert "payment_id" in data["mapping_json"]
        assert data["mapping_json"]["payment_id"] == "transaction_id"

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_get_mapping_after_suggest(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"mapping2_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        resp = client.get(f"/api/column-mappings/{file_id}", headers=user["headers"])
        assert resp.status_code == 200
        assert resp.json()["data"]["uploaded_file_id"] == file_id

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_confirm_mapping_without_edits(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"mapping3_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        resp = client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CONFIRMED"

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_confirm_with_user_edits(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"mapping4_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])

        # User fixes the mapping before confirming
        user_mapping = {**MOCK_AI_SUGGESTION["mapping"], "email": "ignore"}
        resp = client.post(
            f"/api/column-mappings/{file_id}/confirm",
            json={"mapping": user_mapping},
            headers=user["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["mapping_json"]["email"] == "ignore"

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_double_confirm_returns_409(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"mapping5_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        resp = client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        assert resp.status_code == 409

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_normalization_inserts_canonical_rows(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"norm1_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])

        resp = client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["rows_inserted"] == 3
        assert data["canonical_table"] == "payment_records"
        assert data["normalization_status"] == "COMPLETED"

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_canonical_rows_preview(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"norm2_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])

        resp = client.get(f"/api/column-mappings/{file_id}/rows", headers=user["headers"])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["rows"]) == 3
        # Decimal amounts preserved
        row0 = data["rows"][0]
        assert row0["transaction_id"] == "pay_001"
        assert float(row0["gross_amount"]) == pytest.approx(5000.0)

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_double_normalization_returns_409(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"norm3_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])

        resp = client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])
        assert resp.status_code == 409

    @patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping")
    def test_normalize_without_confirm_returns_409(self, mock_suggest, client: TestClient):
        mock_suggest.return_value = MOCK_AI_SUGGESTION
        user = _login(client, f"norm4_{uuid.uuid4().hex[:6]}@x.com")
        file_id = _upload(client, user["headers"])

        client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        # Skip confirm
        resp = client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])
        assert resp.status_code == 409

    def test_cross_workspace_mapping_returns_404(self, client: TestClient):
        alice = _login(client, f"alice_cm_{uuid.uuid4().hex[:6]}@x.com")
        bob = _login(client, f"bob_cm_{uuid.uuid4().hex[:6]}@x.com")

        file_id = _upload(client, alice["headers"])

        resp = client.get(f"/api/column-mappings/{file_id}", headers=bob["headers"])
        assert resp.status_code == 404

    def test_suggest_without_auth_returns_401(self, client: TestClient):
        resp = client.post(f"/api/column-mappings/{uuid.uuid4()}/suggest")
        assert resp.status_code == 401
