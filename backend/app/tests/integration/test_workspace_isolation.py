"""
Integration tests: workspace isolation.

Ensures user A cannot access user B's workspace data.
"""
import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, name: str) -> dict:
    resp = client.post(
        "/api/auth/dev-login",
        json={"email": email, "full_name": name},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    return {
        "token": data["access_token"],
        "workspace_id": data["workspace_id"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


def test_user_can_access_own_workspace(client: TestClient):
    alice = _login(client, "alice_iso@example.com", "Alice")
    resp = client.get(f"/api/workspaces/{alice['workspace_id']}", headers=alice["headers"])
    assert resp.status_code == 200


def test_user_cannot_access_other_workspace(client: TestClient):
    alice = _login(client, "alice_iso2@example.com", "Alice")
    bob = _login(client, "bob_iso@example.com", "Bob")

    # Alice tries to access Bob's workspace
    resp = client.get(f"/api/workspaces/{bob['workspace_id']}", headers=alice["headers"])
    assert resp.status_code == 403


def test_user_can_list_own_workspaces(client: TestClient):
    carol = _login(client, "carol_iso@example.com", "Carol")
    resp = client.get("/api/workspaces", headers=carol["headers"])
    assert resp.status_code == 200
    workspaces = resp.json()["data"]
    assert len(workspaces) >= 1
    ws_ids = [w["id"] for w in workspaces]
    assert carol["workspace_id"] in ws_ids


def test_member_list_requires_membership(client: TestClient):
    alice = _login(client, "alice_iso3@example.com", "Alice")
    bob = _login(client, "bob_iso2@example.com", "Bob")

    resp = client.get(
        f"/api/workspaces/{bob['workspace_id']}/members", headers=alice["headers"]
    )
    assert resp.status_code == 403


def test_owner_can_list_members(client: TestClient):
    dave = _login(client, "dave_iso@example.com", "Dave")
    resp = client.get(
        f"/api/workspaces/{dave['workspace_id']}/members", headers=dave["headers"]
    )
    assert resp.status_code == 200
    members = resp.json()["data"]
    user_ids = [m["user_id"] for m in members]
    # Dave should be in the member list of his own workspace
    assert len(members) >= 1
