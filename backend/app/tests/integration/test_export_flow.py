"""
Integration tests: Phase 6 — XLSX Export.

Tests the full export pipeline:
  1. Run a complete reconciliation (upload → map → normalize → reconcile)
  2. POST /export to generate XLSX
  3. GET  /export to list jobs
  4. GET  /export/{job_id}/download to stream the file
  5. Guards: export on PENDING run → 409, unauthenticated → 401

S3 calls are mocked — LocalStack not required.
"""
import io
import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

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


def _login(client, email):
    resp = client.post("/api/auth/dev-login", json={"email": email})
    d = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {d['access_token']}"}, "workspace_id": d["workspace_id"]}


def _full_pipeline(client, user, csv_bytes, category, mock_return):
    with patch("app.ai.services.ai_column_mapping_service.suggest_column_mapping", return_value=mock_return):
        resp = client.post(
            "/api/uploads", data={"file_category": category},
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
    """Returns a completed run_id."""
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


class TestXLSXExport:

    @patch("app.domain.services.export_service.upload_file")
    @patch("app.domain.services.export_service.download_file")
    def test_full_export_pipeline(self, mock_download, mock_upload, client: TestClient):
        """Generate export, list jobs, download file — full happy path."""
        # We store the uploaded bytes in a local variable to serve as the mock download
        uploaded: list[bytes] = []

        def capture_upload(file_bytes, storage_key, content_type=None):
            uploaded.append(file_bytes)
            return storage_key

        mock_upload.side_effect = capture_upload
        mock_download.side_effect = lambda key: uploaded[0]

        user = _login(client, f"export1_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        # Generate export
        resp = client.post(f"/api/reconciliation-runs/{run_id}/export", headers=user["headers"])
        assert resp.status_code == 201, resp.text
        job_data = resp.json()["data"]
        assert job_data["status"] == "COMPLETED"
        assert job_data["file_name"].endswith(".xlsx")
        assert job_data["file_size_bytes"] > 0
        job_id = job_data["id"]

        # List jobs
        resp = client.get(f"/api/reconciliation-runs/{run_id}/export", headers=user["headers"])
        assert resp.status_code == 200
        jobs = resp.json()["data"]
        assert len(jobs) >= 1
        assert jobs[0]["id"] == job_id

        # Download
        resp = client.get(
            f"/api/reconciliation-runs/{run_id}/export/{job_id}/download",
            headers=user["headers"],
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in resp.headers["content-disposition"]
        # Verify it's a valid XLSX (PK magic bytes)
        assert resp.content[:2] == b"PK"

    @patch("app.domain.services.export_service.upload_file")
    def test_export_scope_matches_only(self, mock_upload, client: TestClient):
        mock_upload.return_value = "exports/test/key.xlsx"
        user = _login(client, f"export2_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/export?scope=MATCHES_ONLY",
            headers=user["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["export_scope"] == "MATCHES_ONLY"
        assert data["exception_rows_exported"] == 0
        assert data["matched_rows_exported"] >= 2

    @patch("app.domain.services.export_service.upload_file")
    def test_export_scope_exceptions_only(self, mock_upload, client: TestClient):
        mock_upload.return_value = "exports/test/key.xlsx"
        user = _login(client, f"export3_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)

        resp = client.post(
            f"/api/reconciliation-runs/{run_id}/export?scope=EXCEPTIONS_ONLY",
            headers=user["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["export_scope"] == "EXCEPTIONS_ONLY"
        assert data["matched_rows_exported"] == 0
        assert data["exception_rows_exported"] >= 1

    def test_export_pending_run_returns_409(self, client: TestClient):
        user = _login(client, f"export4_{uuid.uuid4().hex[:6]}@x.com")
        src_id = _full_pipeline(client, user, STRIPE_CSV, "STRIPE_REPORT", MOCK_STRIPE_MAPPING)
        tgt_id = _full_pipeline(client, user, BANK_CSV, "BANK_STATEMENT", MOCK_BANK_MAPPING)
        resp = client.post(
            "/api/reconciliation-runs",
            json={"name": "Pending", "uploaded_file_ids": [src_id, tgt_id]},
            headers=user["headers"],
        )
        run_id = resp.json()["data"]["id"]
        # No execute call — status = PENDING

        resp = client.post(f"/api/reconciliation-runs/{run_id}/export", headers=user["headers"])
        assert resp.status_code == 409

    def test_export_requires_auth(self, client: TestClient):
        resp = client.post(f"/api/reconciliation-runs/{uuid.uuid4()}/export")
        assert resp.status_code == 401

    def test_download_nonexistent_job_returns_404(self, client: TestClient):
        user = _login(client, f"export5_{uuid.uuid4().hex[:6]}@x.com")
        run_id = _run_reconciliation(client, user)
        resp = client.get(
            f"/api/reconciliation-runs/{run_id}/export/{uuid.uuid4()}/download",
            headers=user["headers"],
        )
        assert resp.status_code == 404
