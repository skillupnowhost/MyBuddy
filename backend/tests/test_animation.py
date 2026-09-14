from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_VECTOR_SCENE_REPLY = (
    '```vector-scene\n'
    '{"objects": ['
    '{"props": {"object_type": "CIRCLE", "cx": 50, "cy": 50, "r": 20, "fill": "#ff0000"}, "z_index": 0}, '
    '{"props": {"object_type": "TEXT", "x": 10, "y": 10, "content": "hi"}, "z_index": 1}'
    ']}\n'
    '```'
)

VALID_KEYFRAMES_REPLY = (
    '```animation-keyframes\n'
    '{"keyframes": ['
    '{"object_index": 0, "time_ms": 0, "prop": "cx", "value": 50, "easing": "LINEAR"}, '
    '{"object_index": 0, "time_ms": 2000, "prop": "cx", "value": 300, "easing": "EASE_IN_OUT"}'
    ']}\n'
    '```'
)

INVALID_REPLY = "sorry, I cannot help with that."


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


def test_generate_animation_creates_keyframes_from_valid_reply(client, db_session):
    token = _register_and_login(client, "anim-gen@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        resp = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move the circle to the right"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["keyframes"]) == 2
        assert body["keyframes"][0]["prop"] == "cx"
    finally:
        _clear_mock()


def test_generate_animation_retries_once_on_invalid_reply_then_succeeds(client, db_session):
    token = _register_and_login(client, "anim-retry@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)

    mock = MockProvider(replies=[INVALID_REPLY, VALID_KEYFRAMES_REPLY])
    _use_mock(mock)
    try:
        resp = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move the circle"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert mock.call_count == 2
    finally:
        _clear_mock()


def test_generate_animation_fails_clearly_after_exhausting_retries(client, db_session):
    token = _register_and_login(client, "anim-fail@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)

    _use_mock(MockProvider(reply=INVALID_REPLY))
    try:
        resp = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "do something"},
            headers=headers,
        )
        assert resp.status_code == 502
        assert "could not produce valid keyframes" in resp.json()["detail"]
    finally:
        _clear_mock()


def test_manual_keyframe_crud(client, db_session):
    token = _register_and_login(client, "anim-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)
    circle_id = next(o["id"] for o in doc["objects"] if o["object_type"] == "CIRCLE")

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it"},
            headers=headers,
        ).json()
    finally:
        _clear_mock()

    added = client.post(
        f"/api/v1/animation/documents/{anim['id']}/keyframes",
        json={"object_id": circle_id, "time_ms": 1000, "prop": "fill", "value": "#00ff00", "easing": "LINEAR"},
        headers=headers,
    )
    assert added.status_code == 201
    kf_id = added.json()["id"]

    patched = client.patch(
        f"/api/v1/animation/documents/{anim['id']}/keyframes/{kf_id}",
        json={"value": "#0000ff"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["value"] == "#0000ff"

    deleted = client.delete(f"/api/v1/animation/documents/{anim['id']}/keyframes/{kf_id}", headers=headers)
    assert deleted.status_code == 204


def test_keyframe_rejects_non_animatable_prop(client, db_session):
    token = _register_and_login(client, "anim-badprop@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)
    text_id = next(o["id"] for o in doc["objects"] if o["object_type"] == "TEXT")

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it"},
            headers=headers,
        ).json()
    finally:
        _clear_mock()

    resp = client.post(
        f"/api/v1/animation/documents/{anim['id']}/keyframes",
        json={"object_id": text_id, "time_ms": 0, "prop": "content", "value": "bye"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_keyframe_rejects_invalid_value(client, db_session):
    token = _register_and_login(client, "anim-badvalue@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)
    circle_id = next(o["id"] for o in doc["objects"] if o["object_type"] == "CIRCLE")

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it"},
            headers=headers,
        ).json()
    finally:
        _clear_mock()

    resp = client.post(
        f"/api/v1/animation/documents/{anim['id']}/keyframes",
        json={"object_id": circle_id, "time_ms": 0, "prop": "fill", "value": "javascript:alert(1)"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_export_contains_keyframes_style_and_animation_property(client, db_session):
    token = _register_and_login(client, "anim-export@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it"},
            headers=headers,
        ).json()
    finally:
        _clear_mock()

    resp = client.get(f"/api/v1/animation/documents/{anim['id']}/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<style>" in resp.text
    assert "@keyframes" in resp.text
    assert "animation:" in resp.text


def test_animation_requires_owned_vector_document(client, db_session):
    token_a = _register_and_login(client, "anim-src-owner@example.com")
    token_b = _register_and_login(client, "anim-src-intruder@example.com")
    doc = _create_vector_document(client, {"Authorization": f"Bearer {token_a}"})

    resp = client.post(
        "/api/v1/animation/documents",
        json={"vector_document_id": doc["id"], "prompt": "move it"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_animation_isolated_per_user(client, db_session):
    token_a = _register_and_login(client, "anim-owner@example.com")
    token_b = _register_and_login(client, "anim-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    doc = _create_vector_document(client, headers_a)

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it"},
            headers=headers_a,
        ).json()
    finally:
        _clear_mock()

    forbidden = client.get(
        f"/api/v1/animation/documents/{anim['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden.status_code == 404


def test_duration_and_keyframe_count_are_capped(client, db_session, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "animation_max_duration_ms", 500)

    token = _register_and_login(client, "anim-cap@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    doc = _create_vector_document(client, headers)

    resp = client.post(
        "/api/v1/animation/documents",
        json={"vector_document_id": doc["id"], "prompt": "move it", "duration_ms": 999999},
        headers=headers,
    )
    assert resp.status_code == 400
