from app.core.config import get_settings
from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

# Imported at module level (collection time), not inside a test function — see
# test_motion.py for why an in-function get_settings() call can silently fetch a stale
# cached instance after test_admin.py/test_sandbox.py call get_settings.cache_clear().
settings = get_settings()

VALID_VECTOR_SCENE_REPLY = (
    '```vector-scene\n'
    '{"objects": [{"props": {"object_type": "CIRCLE", "cx": 50, "cy": 50, "r": 20, "fill": "#ff0000"}, "z_index": 0}]}\n'
    '```'
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _use_mock(mock):
    app.dependency_overrides[get_llm_client] = lambda: mock


def _clear_mock():
    app.dependency_overrides.pop(get_llm_client, None)


def _create_vector_document(client, headers):
    _use_mock(MockProvider(reply=VALID_VECTOR_SCENE_REPLY))
    try:
        return client.post("/api/v1/vector/documents", json={"prompt": "a red circle"}, headers=headers).json()
    finally:
        _clear_mock()


def test_create_brand_kit_validates_colors(client):
    token = _register_and_login(client, "creative-badcolor@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/creative/brand-kits",
        json={"name": "Acme", "primary_color": "javascript:alert(1)"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_create_project_with_brand_kit(client):
    token = _register_and_login(client, "creative-project@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kit = client.post(
        "/api/v1/creative/brand-kits",
        json={"name": "Acme", "primary_color": "#112233", "font_family": "Inter"},
        headers=headers,
    ).json()

    project = client.post(
        "/api/v1/creative/projects", json={"title": "Rebrand", "brand_kit_id": kit["id"]}, headers=headers
    )
    assert project.status_code == 201
    assert project.json()["brand_kit_id"] == kit["id"]


def test_manual_asset_attach_and_detach(client, db_session):
    token = _register_and_login(client, "creative-attach@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers).json()

    attached = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "VECTOR", "asset_id": doc["id"], "label": "Logo"},
        headers=headers,
    )
    assert attached.status_code == 201
    asset_id = attached.json()["id"]

    detached = client.delete(f"/api/v1/creative/projects/{project['id']}/assets/{asset_id}", headers=headers)
    assert detached.status_code == 204

    # The underlying document must still exist after detach.
    still_there = client.get(f"/api/v1/vector/documents/{doc['id']}", headers=headers)
    assert still_there.status_code == 200


def test_attach_rejects_unowned_asset(client, db_session):
    token_a = _register_and_login(client, "creative-asset-owner@example.com")
    token_b = _register_and_login(client, "creative-asset-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    doc = _create_vector_document(client, headers_a)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers_b).json()

    resp = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "VECTOR", "asset_id": doc["id"]},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_asset_count_is_capped(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "creative_max_assets_per_project", 1)

    token = _register_and_login(client, "creative-cap@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc1 = _create_vector_document(client, headers)
    doc2 = _create_vector_document(client, headers)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers).json()

    first = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "VECTOR", "asset_id": doc1["id"]},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "VECTOR", "asset_id": doc2["id"]},
        headers=headers,
    )
    assert second.status_code == 400


def test_generate_asset_creates_vector_document_and_attaches_it(client, db_session):
    token = _register_and_login(client, "creative-generate@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers).json()

    _use_mock(MockProvider(reply=VALID_VECTOR_SCENE_REPLY))
    try:
        resp = client.post(
            f"/api/v1/creative/projects/{project['id']}/assets/generate",
            json={"prompt": "a red circle", "purpose": "LOGO", "label": "Logo"},
            headers=headers,
        )
        assert resp.status_code == 201
        document_id = resp.json()["id"]
    finally:
        _clear_mock()

    updated_project = client.get(f"/api/v1/creative/projects/{project['id']}", headers=headers).json()
    assert len(updated_project["assets"]) == 1
    assert updated_project["assets"][0]["asset_type"] == "VECTOR"
    assert updated_project["assets"][0]["asset_id"] == document_id
    assert updated_project["assets"][0]["label"] == "Logo"

    doc_resp = client.get(f"/api/v1/vector/documents/{document_id}", headers=headers)
    assert doc_resp.status_code == 200


def test_generate_asset_injects_brand_guidance_into_the_prompt(client, db_session):
    token = _register_and_login(client, "creative-brandprompt@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    kit = client.post(
        "/api/v1/creative/brand-kits", json={"name": "Acme", "primary_color": "#abcdef"}, headers=headers
    ).json()
    project = client.post(
        "/api/v1/creative/projects", json={"title": "P", "brand_kit_id": kit["id"]}, headers=headers
    ).json()

    mock = MockProvider(reply=VALID_VECTOR_SCENE_REPLY)
    _use_mock(mock)
    try:
        resp = client.post(
            f"/api/v1/creative/projects/{project['id']}/assets/generate",
            json={"prompt": "a logo"},
            headers=headers,
        )
        assert resp.status_code == 201
    finally:
        _clear_mock()

    assert mock.last_messages is not None
    user_message = next(m for m in mock.last_messages if m["role"] == "user")
    assert "#abcdef" in user_message["content"]


def test_creative_project_isolated_per_user(client):
    token_a = _register_and_login(client, "creative-owner@example.com")
    token_b = _register_and_login(client, "creative-intruder@example.com")
    project = client.post(
        "/api/v1/creative/projects", json={"title": "P"}, headers={"Authorization": f"Bearer {token_a}"}
    ).json()

    forbidden = client.get(
        f"/api/v1/creative/projects/{project['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden.status_code == 404
