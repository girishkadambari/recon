"""
Integration tests: upload flow.

Tests the full upload → parse → source records pipeline.
Uses real Postgres + LocalStack S3.
"""
import io
import pytest
from fastapi.testclient import TestClient


SAMPLE_CSV = b"""payment_id,amount,currency,status
pay_001,5000.00,INR,succeeded
pay_002,12000.00,INR,succeeded
pay_003,3500.00,INR,failed
"""


def _login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/dev-login", json={"email": email})
    d = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {d['access_token']}"}, "workspace_id": d["workspace_id"]}


class TestUploadFlow:
    def test_upload_csv_succeeds(self, client: TestClient):
        user = _login(client, "upload_test1@example.com")
        resp = client.post(
            "/api/uploads",
            data={"file_category": "STRIPE_REPORT"},
            files={"file": ("stripe_report.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=user["headers"],
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["file_name"] == "stripe_report.csv"
        assert data["status"] == "PARSED"
        assert data["row_count"] == 3
        assert data["workspace_id"] == user["workspace_id"]

    def test_upload_invalid_category_returns_422(self, client: TestClient):
        user = _login(client, "upload_test2@example.com")
        resp = client.post(
            "/api/uploads",
            data={"file_category": "INVALID_CATEGORY"},
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=user["headers"],
        )
        assert resp.status_code == 422

    def test_upload_without_auth_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/uploads",
            data={"file_category": "STRIPE_REPORT"},
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        assert resp.status_code == 401

    def test_list_uploads_returns_workspace_files_only(self, client: TestClient):
        alice = _login(client, "alice_upload@example.com")
        bob = _login(client, "bob_upload@example.com")

        # Alice uploads a file
        client.post(
            "/api/uploads",
            data={"file_category": "BANK_STATEMENT"},
            files={"file": ("bank.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=alice["headers"],
        )

        # Bob lists uploads — should not see Alice's
        resp = client.get("/api/uploads", headers=bob["headers"])
        assert resp.status_code == 200
        ids = [f["workspace_id"] for f in resp.json()["data"]]
        assert all(i == bob["workspace_id"] for i in ids)

    def test_get_upload_by_id(self, client: TestClient):
        user = _login(client, "get_test@example.com")
        upload_resp = client.post(
            "/api/uploads",
            data={"file_category": "INVOICE_EXPORT"},
            files={"file": ("inv.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=user["headers"],
        )
        file_id = upload_resp.json()["data"]["id"]

        resp = client.get(f"/api/uploads/{file_id}", headers=user["headers"])
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == file_id

    def test_preview_returns_rows(self, client: TestClient):
        user = _login(client, "preview_test@example.com")
        upload_resp = client.post(
            "/api/uploads",
            data={"file_category": "RAZORPAY_REPORT"},
            files={"file": ("razorpay.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=user["headers"],
        )
        assert upload_resp.status_code == 201
        file_id = upload_resp.json()["data"]["id"]

        resp = client.get(f"/api/uploads/{file_id}/preview?n=2", headers=user["headers"])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["rows"]) == 2
        assert "payment_id" in data["column_names"]
        assert data["total_rows"] == 3

    def test_delete_upload(self, client: TestClient):
        user = _login(client, "delete_test@example.com")
        upload_resp = client.post(
            "/api/uploads",
            data={"file_category": "STRIPE_REPORT"},
            files={"file": ("del.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=user["headers"],
        )
        file_id = upload_resp.json()["data"]["id"]

        del_resp = client.delete(f"/api/uploads/{file_id}", headers=user["headers"])
        assert del_resp.status_code == 200

        # Subsequent get should 404
        get_resp = client.get(f"/api/uploads/{file_id}", headers=user["headers"])
        assert get_resp.status_code == 404

    def test_cross_workspace_access_denied(self, client: TestClient):
        alice = _login(client, "alice_xws@example.com")
        bob = _login(client, "bob_xws@example.com")

        upload_resp = client.post(
            "/api/uploads",
            data={"file_category": "STRIPE_REPORT"},
            files={"file": ("alice.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
            headers=alice["headers"],
        )
        file_id = upload_resp.json()["data"]["id"]

        # Bob tries to access Alice's file
        resp = client.get(f"/api/uploads/{file_id}", headers=bob["headers"])
        assert resp.status_code == 404  # not 403 — don't leak existence
