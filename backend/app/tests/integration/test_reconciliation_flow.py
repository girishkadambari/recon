"""
Integration tests: reconciliation flow.

Tests the full reconciliation pipeline:
  1. Upload two CSV files (source + target)
  2. Map and normalize both
  3. Create a reconciliation run
  4. Execute the run
  5. Inspect matches and exceptions
  6. Review a match, resolve an exception

AI is mocked — no ANTHROPIC_API_KEY needed.
"""
import io
import uuid
import pytest
from decimal import Decimal
from unittest.mock import patch
from fastapi.testclient import TestClient

# Source: Stripe-style payment report
STRIPE_CSV = b"""payment_id,amount,currency,status,created_at
pay_001,5000.00,INR,succeeded,2024-01-15
pay_002,12000.00,INR,succeeded,2024-01-16
pay_003,3500.00,INR,failed,2024-01-17
pay_004,8000.00,INR,succeeded,2024-01-18
"""

# Target: Bank statement (3 out of 4 payments landed)
BANK_CSV = b"""utr,credit_amount,currency,narration,transaction_date
pay_001,5000.00,INR,STRIPE SETTLEMENT,2024-01-15
pay_002,12000.00,INR,STRIPE SETTLEMENT,2024-01-16
pay_004,8000.00,INR,STRIPE SETTLEMENT,2024-01-18
BANK_EXTRA,750.00,INR,MISC CREDIT,2024-01-19
"""

MOCK_STRIPE_MAPPING = {
    "mapping": {
        "payment_id": "transaction_id",
        "amount": "gross_amount",
        "currency": "currency",
        "status": "status",
        "created_at": "transaction_date",
    },
    "confidence_score": 95,
    "notes": "",
}

MOCK_BANK_MAPPING = {
    "mapping": {
        "utr": "utr",
        "credit_amount": "credit_amount",
        "currency": "currency",
        "narration": "narration",
        "transaction_date": "transaction_date",
    },
    "confidence_score": 90,
    "notes": "",
}


def _login(client, email):
    resp = client.post("/api/auth/dev-login", json={"email": email})
    d = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {d['access_token']}"}, "workspace_id": d["workspace_id"]}


def _full_pipeline(client, user, csv_bytes, category, mock_return):
    """Upload → suggest mapping → confirm → normalize. Returns file_id."""
    with patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping", return_value=mock_return):
        # Upload
        resp = client.post(
            "/api/uploads",
            data={"file_category": category},
            files={"file": ("file.csv", io.BytesIO(csv_bytes), "text/csv")},
            headers=user["headers"],
        )
        assert resp.status_code == 201, resp.text
        file_id = resp.json()["data"]["id"]
        # Suggest
        resp = client.post(f"/api/column-mappings/{file_id}/suggest", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        # Confirm
        resp = client.post(f"/api/column-mappings/{file_id}/confirm", headers=user["headers"])
        assert resp.status_code == 200
        # Normalize
        resp = client.post(f"/api/column-mappings/{file_id}/normalize", headers=user["headers"])
        assert resp.status_code == 200, resp.text
    return file_id


class TestReconciliationFlow:

    def test_create_run_requires_normalized_files(self, client: TestClient):
        user = _login(client, f"recon_guard_{uuid.uuid4().hex[:6]}@x.com")
        # Upload raw files (not normalized)
        for cat in ["STRIPE_REPORT", "BANK_STATEMENT"]:
            resp = client.post(
                "/api/uploads",
                data={"file_category": cat},
                files={"file": ("f.csv", io.BytesIO(STRIPE_CSV), "text/csv")},
                headers=user["headers"],
            )
            assert resp.status_code == 201

        file_ids = client.get("/api/uploads", headers=user["headers"]).json()["data"]
        src_id, tgt_id = file_ids[0]["id"], file_ids[1]["id"]

        resp = client.post(
            "/api/reconciliation-runs",
            json={"name": "test run", "uploaded_file_ids": [src_id, tgt_id]},
            headers=user["headers"],
        )
        assert resp.status_code == 409  # not normalized yet

    def test_full_reconciliation_pipeline(self, client: TestClient):
        user = _login(client, f"recon_full_{uuid.uuid4().hex[:6]}@x.com")

        # Pipeline: Upload → map → normalize for both files
        src_id = _full_pipeline(client, user, STRIPE_CSV, "STRIPE_REPORT", MOCK_STRIPE_MAPPING)
        tgt_id = _full_pipeline(client, user, BANK_CSV, "BANK_STATEMENT", MOCK_BANK_MAPPING)

        # Create run
        resp = client.post(
            "/api/reconciliation-runs",
            json={"name": "Jan 2024 Recon", "uploaded_file_ids": [src_id, tgt_id]},
            headers=user["headers"],
        )
        assert resp.status_code == 201
        run_id = resp.json()["data"]["id"]
        assert resp.json()["data"]["status"] == "PENDING"

        # Execute
        resp = client.post(f"/api/reconciliation-runs/{run_id}/run", headers=user["headers"])
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "COMPLETED"
        assert data["matched_count"] >= 3   # pay_001, pay_002, pay_004
        assert data["exception_count"] >= 2  # pay_003 (failed) + BANK_EXTRA

        # List runs
        resp = client.get("/api/reconciliation-runs", headers=user["headers"])
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

        # Get run
        resp = client.get(f"/api/reconciliation-runs/{run_id}", headers=user["headers"])
        assert resp.status_code == 200
        assert resp.json()["data"]["match_rate_pct"] > 50

        # Matches
        resp = client.get(f"/api/reconciliation-runs/{run_id}/matches", headers=user["headers"])
        assert resp.status_code == 200
        matches = resp.json()["data"]
        assert len(matches) >= 3

        # Review a match
        match_id = matches[0]["id"]
        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/matches/{match_id}/review",
            json={"action": "APPROVED", "note": "Looks correct"},
            headers=user["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"

        # Exceptions
        resp = client.get(f"/api/reconciliation-runs/{run_id}/exceptions", headers=user["headers"])
        assert resp.status_code == 200
        exceptions = resp.json()["data"]
        assert len(exceptions) >= 1

        # Resolve an exception
        exc_id = exceptions[0]["id"]
        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/exceptions/{exc_id}/resolve",
            json={"status": "WAIVED", "note": "Known difference"},
            headers=user["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "WAIVED"

    def test_double_execute_returns_409(self, client: TestClient):
        user = _login(client, f"recon_dbl_{uuid.uuid4().hex[:6]}@x.com")
        src_id = _full_pipeline(client, user, STRIPE_CSV, "STRIPE_REPORT", MOCK_STRIPE_MAPPING)
        tgt_id = _full_pipeline(client, user, BANK_CSV, "BANK_STATEMENT", MOCK_BANK_MAPPING)

        resp = client.post(
            "/api/reconciliation-runs",
            json={"name": "Dbl Run", "uploaded_file_ids": [src_id, tgt_id]},
            headers=user["headers"],
        )
        run_id = resp.json()["data"]["id"]
        client.post(f"/api/reconciliation-runs/{run_id}/run", headers=user["headers"])
        resp2 = client.post(f"/api/reconciliation-runs/{run_id}/run", headers=user["headers"])
        assert resp2.status_code == 409

    def test_cross_workspace_run_not_visible(self, client: TestClient):
        alice = _login(client, f"alice_recon_{uuid.uuid4().hex[:6]}@x.com")
        bob = _login(client, f"bob_recon_{uuid.uuid4().hex[:6]}@x.com")

        # Alice can't see Bob's runs (if Bob had any)
        resp = client.get("/api/reconciliation-runs", headers=alice["headers"])
        assert resp.status_code == 200
        for r in resp.json()["data"]:
            assert r["workspace_id"] == alice["workspace_id"]

    def test_run_without_auth_returns_401(self, client: TestClient):
        resp = client.post("/api/reconciliation-runs", json={
            "name": "x", "uploaded_file_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
        })
        assert resp.status_code == 401
