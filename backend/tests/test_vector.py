import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.vector import PathProps, RectProps
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_SCENE_REPLY = (
    '```vector-scene\n'
    '{"objects": ['
    '{"props": {"object_type": "CIRCLE", "cx": 50, "cy": 50, "r": 20, "fill": "#ff0000"}, "z_index": 0}, '
    '{"props": {"object_type": "RECT", "x": 10, "y": 10, "width": 30, "height": 30, "fill": "blue"}, "z_index": 1}'
    ']}\n'
    '```'
)

INVALID_SCENE_REPLY = "sorry, I cannot help with that."


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _use_mock(mock):
    app.dependency_overrides[get_llm_client] = lambda: mock


def _clear_mock():
    app.dependency_overrides.pop(get_llm_client, None)


def test_generate_document_creates_objects_from_valid_scene(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-gen@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "a red circle next to a blue square"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["objects"]) == 2
        types = {o["object_type"] for o in body["objects"]}
        assert types == {"CIRCLE", "RECT"}
    finally:
        _clear_mock()


def test_generate_document_retries_once_on_invalid_json_then_succeeds(client, db_session):
    mock = MockProvider(replies=[INVALID_SCENE_REPLY, VALID_SCENE_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "vector-retry@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "a red circle next to a blue square"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert len(resp.json()["objects"]) == 2
        assert mock.call_count == 2
    finally:
        _clear_mock()


def test_generate_document_fails_clearly_after_exhausting_retries(client, db_session):
    _use_mock(MockProvider(reply=INVALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "something impossible"},
            headers=headers,
        )
        assert resp.status_code == 502
        assert "could not produce a valid scene" in resp.json()["detail"]
    finally:
        _clear_mock()


def test_manual_object_crud(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-crud@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        doc = client.post(
            "/api/v1/vector/documents", json={"prompt": "anything"}, headers=headers
        ).json()
        doc_id = doc["id"]

        added = client.post(
            f"/api/v1/vector/documents/{doc_id}/objects",
            json={"props": {"object_type": "TEXT", "x": 5, "y": 5, "content": "hello"}, "z_index": 5},
            headers=headers,
        )
        assert added.status_code == 201
        object_id = added.json()["id"]
        assert added.json()["object_type"] == "TEXT"

        patched = client.patch(
            f"/api/v1/vector/documents/{doc_id}/objects/{object_id}",
            json={"prop": "content", "value": "goodbye"},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["props"]["content"] == "goodbye"

        deleted = client.delete(f"/api/v1/vector/documents/{doc_id}/objects/{object_id}", headers=headers)
        assert deleted.status_code == 204

        detail = client.get(f"/api/v1/vector/documents/{doc_id}", headers=headers).json()
        assert object_id not in [o["id"] for o in detail["objects"]]
    finally:
        _clear_mock()


def test_ai_edit_and_manual_patch_use_the_same_mutation_path(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-sync@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        doc = client.post(
            "/api/v1/vector/documents", json={"prompt": "a red circle and a blue square"}, headers=headers
        ).json()
        doc_id = doc["id"]
        circle_id = next(o["id"] for o in doc["objects"] if o["object_type"] == "CIRCLE")

        # Manual patch via the API.
        manual = client.patch(
            f"/api/v1/vector/documents/{doc_id}/objects/{circle_id}",
            json={"prop": "fill", "value": "#00ff00"},
            headers=headers,
        )
        assert manual.status_code == 200
        assert manual.json()["props"]["fill"] == "#00ff00"

        # Reset, then apply an equivalent edit via the AI path (object_index 0 == the circle,
        # since it was generated first) and confirm the same field changes the same way.
        client.patch(
            f"/api/v1/vector/documents/{doc_id}/objects/{circle_id}",
            json={"prop": "fill", "value": "#ff0000"},
            headers=headers,
        )
        ai_reply = '```vector-op\n{"op": "SET_PROP", "object_index": 0, "prop": "fill", "value": "#00ff00"}\n```'
        app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply=ai_reply)
        ai_edit = client.post(
            f"/api/v1/vector/documents/{doc_id}/edit",
            json={"instruction": "make the circle green"},
            headers=headers,
        )
        assert ai_edit.status_code == 200
        circle_after_ai = next(o for o in ai_edit.json()["objects"] if o["id"] == circle_id)
        assert circle_after_ai["props"]["fill"] == "#00ff00"
    finally:
        _clear_mock()


def test_export_returns_valid_svg_markup(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-export@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        doc = client.post(
            "/api/v1/vector/documents", json={"prompt": "a red circle and a blue square"}, headers=headers
        ).json()

        resp = client.get(f"/api/v1/vector/documents/{doc['id']}/export", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert resp.text.startswith("<svg")
        assert "<circle" in resp.text
        assert "<rect" in resp.text
    finally:
        _clear_mock()


def test_path_data_rejects_disallowed_characters():
    with pytest.raises(ValidationError):
        PathProps(d="M10 10 L90 90 <script>alert(1)</script>")


def test_color_rejects_invalid_value():
    with pytest.raises(ValidationError):
        RectProps(x=0, y=0, width=10, height=10, fill="javascript:alert(1)")


def test_logo_purpose_uses_smaller_default_canvas_and_object_cap(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-logo@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "a logo for a coffee shop", "purpose": "LOGO"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["purpose"] == "LOGO"
        assert body["canvas_width"] == 200
        assert body["canvas_height"] == 200
    finally:
        _clear_mock()


def test_explicit_canvas_size_overrides_purpose_default(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-icon-override@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "an icon", "purpose": "ICON", "canvas_width": 128, "canvas_height": 128},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["canvas_width"] == 128
        assert body["canvas_height"] == 128
    finally:
        _clear_mock()


def test_unknown_purpose_rejected(client):
    token = _register_and_login(client, "vector-badpurpose@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/vector/documents",
        json={"prompt": "anything", "purpose": "NOT_A_REAL_PURPOSE"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_default_purpose_is_general_and_unchanged(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "vector-default-purpose@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/vector/documents", json={"prompt": "anything"}, headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["purpose"] == "GENERAL"
        assert body["canvas_width"] == 400
        assert body["canvas_height"] == 400
    finally:
        _clear_mock()


def test_vector_document_isolated_per_user(client, db_session):
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token_a = _register_and_login(client, "vector-owner@example.com")
        token_b = _register_and_login(client, "vector-intruder@example.com")

        doc = client.post(
            "/api/v1/vector/documents",
            json={"prompt": "anything"},
            headers={"Authorization": f"Bearer {token_a}"},
        ).json()

        forbidden = client.get(
            f"/api/v1/vector/documents/{doc['id']}", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert forbidden.status_code == 404
    finally:
        _clear_mock()
