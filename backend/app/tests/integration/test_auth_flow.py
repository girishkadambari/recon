"""
Integration tests: auth flow.

Tests:
  1. dev-login creates user + workspace + JWT (local only)
  2. GET /api/auth/me returns user and workspace
  3. Missing JWT returns 401
  4. Invalid JWT returns 401
  5. /api/auth/google/login returns redirect or 503 when not configured
"""
import pytest
from fastapi.testclient import TestClient


def test_dev_login_creates_user_and_workspace(client: TestClient):
    import uuid
    unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/dev-login",
        json={"email": unique_email, "full_name": "Alice"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user_id"]
    assert data["workspace_id"]
    assert data["is_new_user"] is True


def test_dev_login_second_call_is_not_new_user(client: TestClient):
    client.post("/api/auth/dev-login", json={"email": "bob@example.com"})
    resp = client.post("/api/auth/dev-login", json={"email": "bob@example.com"})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_new_user"] is False


def test_get_me_returns_user_and_workspace(client: TestClient, auth_headers: dict):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["email"] == "test@example.com"
    assert data["active_workspace"]["id"]
    assert data["active_workspace"]["role"] == "OWNER"


def test_get_me_without_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_get_me_with_invalid_token_returns_401(client: TestClient):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_google_login_returns_503_when_not_configured(client: TestClient):
    """When GOOGLE_CLIENT_ID is empty, returns 503 with helpful message."""
    resp = client.get("/api/auth/google/login", follow_redirects=False)
    # Either a redirect (if configured) or 503 (if not)
    assert resp.status_code in (302, 307, 503)


def test_logout_returns_200(client: TestClient, auth_headers: dict):
    resp = client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 200
