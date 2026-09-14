import io

from app.core.config import get_settings
from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

settings = get_settings()

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_rejects_unsupported_image_type(client):
    token = _register_and_login(client, "bad-image@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/images",
        headers=headers,
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
    )
    assert resp.status_code == 415


def test_rejects_empty_image(client):
    token = _register_and_login(client, "empty-image@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/images",
        headers=headers,
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
    )
    assert resp.status_code == 400


def test_rejects_oversized_image(client, monkeypatch):
    monkeypatch.setattr(settings, "max_image_size_bytes", 10)
    token = _register_and_login(client, "big-image@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/images",
        headers=headers,
        files={"file": ("big.png", io.BytesIO(_PNG_BYTES), "image/png")},
    )
    assert resp.status_code == 413


def test_image_access_is_isolated_per_user(client):
    token_a = _register_and_login(client, "image-owner@example.com")
    token_b = _register_and_login(client, "image-intruder@example.com")

    resp = client.post(
        "/api/v1/images",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("private.png", io.BytesIO(_PNG_BYTES), "image/png")},
    )
    image_id = resp.json()["id"]

    forbidden = client.get(f"/api/v1/images/{image_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


def test_delete_unattached_image_succeeds(client):
    token = _register_and_login(client, "deleter-image@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/images", headers=headers, files={"file": ("a.png", io.BytesIO(_PNG_BYTES), "image/png")}
    )
    image_id = resp.json()["id"]

    deleted = client.delete(f"/api/v1/images/{image_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/images/{image_id}", headers=headers).status_code == 404


def test_message_with_image_uses_vision_model_and_attaches_image(client, db_session):
    mock = MockProvider(reply="I see a small image.")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "vision-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        image_resp = client.post(
            "/api/v1/images", headers=headers, files={"file": ("shot.png", io.BytesIO(_PNG_BYTES), "image/png")}
        )
        image_id = image_resp.json()["id"]

        conv = client.post("/api/v1/conversations", json={}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "What is this?", "image_ids": [image_id]},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            "".join(resp.iter_text())

        assert mock.last_model == settings.ollama_vision_model

        history = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=headers).json()
        user_message = next(m for m in history if m["role"] == "user")
        assert len(user_message["images"]) == 1
        assert user_message["images"][0]["id"] == image_id

        # The image is now attached — it can no longer be deleted, and it can no longer be
        # reused on a second message.
        assert client.delete(f"/api/v1/images/{image_id}", headers=headers).status_code == 400

        second = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Again?", "image_ids": [image_id]},
            headers=headers,
        )
        assert second.status_code == 404
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_text_only_message_uses_conversations_normal_model(client, db_session):
    mock = MockProvider(reply="Hello!")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "textonly-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Hi there"},
            headers=headers,
        ) as resp:
            "".join(resp.iter_text())

        assert mock.last_model == settings.ollama_model
        assert mock.last_model != settings.ollama_vision_model
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_cannot_attach_another_users_image(client):
    token_a = _register_and_login(client, "img-owner2@example.com")
    token_b = _register_and_login(client, "img-intruder2@example.com")

    image_resp = client.post(
        "/api/v1/images",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("a.png", io.BytesIO(_PNG_BYTES), "image/png")},
    )
    image_id = image_resp.json()["id"]

    conv = client.post("/api/v1/conversations", json={}, headers={"Authorization": f"Bearer {token_b}"})
    conv_id = conv.json()["id"]

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "steal", "image_ids": [image_id]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
