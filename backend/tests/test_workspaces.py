from app.core.config import get_settings
from app.db.models.conversation import Conversation
from app.db.models.creative_project import CreativeProject

settings = get_settings()


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_create_list_get_patch_delete_workspace(client):
    token = _register_and_login(client, "workspace-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/v1/workspaces", json={"name": "Sci-fi trailer", "description": "shots + vfx"}, headers=headers)
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    listed = client.get("/api/v1/workspaces", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["conversations"] == []
    assert fetched.json()["creative_projects"] == []

    patched = client.patch(f"/api/v1/workspaces/{workspace_id}", json={"name": "Renamed"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"

    deleted = client.delete(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers).status_code == 404


def test_workspace_isolated_between_users(client):
    token_a = _register_and_login(client, "workspace-owner@example.com")
    token_b = _register_and_login(client, "workspace-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    created = client.post("/api/v1/workspaces", json={"name": "private"}, headers=headers_a)
    workspace_id = created.json()["id"]

    assert client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers_b).status_code == 404
    assert client.patch(f"/api/v1/workspaces/{workspace_id}", json={"name": "hijacked"}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/workspaces/{workspace_id}", headers=headers_b).status_code == 404


def test_conversation_can_be_assigned_to_owned_workspace(client, db_session):
    token = _register_and_login(client, "conv-workspace@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspace_id = client.post("/api/v1/workspaces", json={"name": "proj"}, headers=headers).json()["id"]

    conv = client.post("/api/v1/conversations", json={"workspace_id": workspace_id}, headers=headers)
    assert conv.status_code == 201
    assert conv.json()["workspace_id"] == workspace_id

    detail = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert len(detail.json()["conversations"]) == 1
    assert detail.json()["conversations"][0]["id"] == conv.json()["id"]


def test_conversation_create_rejects_other_users_workspace(client):
    token_a = _register_and_login(client, "workspace-owner-2@example.com")
    token_b = _register_and_login(client, "workspace-intruder-2@example.com")
    workspace_id = client.post(
        "/api/v1/workspaces", json={"name": "private"}, headers={"Authorization": f"Bearer {token_a}"}
    ).json()["id"]

    resp = client.post(
        "/api/v1/conversations", json={"workspace_id": workspace_id}, headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


def test_creative_project_can_be_assigned_to_workspace(client):
    token = _register_and_login(client, "creative-workspace@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspace_id = client.post("/api/v1/workspaces", json={"name": "proj"}, headers=headers).json()["id"]

    project = client.post(
        "/api/v1/creative/projects", json={"title": "Trailer assets", "workspace_id": workspace_id}, headers=headers
    )
    assert project.status_code == 201
    assert project.json()["workspace_id"] == workspace_id

    detail = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert len(detail.json()["creative_projects"]) == 1


def test_deleting_workspace_keeps_its_conversation_and_creative_project(client, db_session):
    """workspace_id is ondelete="SET NULL", not CASCADE, so deleting a workspace must never
    delete its contents. The actual re-nulling of workspace_id is a real Postgres FK
    behavior this SQLite-backed test suite can't observe (SQLite doesn't enforce FK actions
    without PRAGMA foreign_keys=ON, which this app doesn't set) — same honestly-documented
    gap as every other ondelete="SET NULL" column in this codebase, none of which are
    cascade-tested here either. What's actually verified: the rows survive the delete."""
    token = _register_and_login(client, "workspace-delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspace_id = client.post("/api/v1/workspaces", json={"name": "proj"}, headers=headers).json()["id"]

    conv_id = client.post("/api/v1/conversations", json={"workspace_id": workspace_id}, headers=headers).json()["id"]
    project_id = client.post(
        "/api/v1/creative/projects", json={"title": "assets", "workspace_id": workspace_id}, headers=headers
    ).json()["id"]

    assert client.delete(f"/api/v1/workspaces/{workspace_id}", headers=headers).status_code == 204

    db_session.expire_all()
    assert db_session.get(Conversation, conv_id) is not None
    assert db_session.get(CreativeProject, project_id) is not None
