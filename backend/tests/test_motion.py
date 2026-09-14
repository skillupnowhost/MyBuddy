from app.core.config import get_settings
from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

# Imported at module level (collection time), not inside a test function, so this stays the
# same Settings instance app.api.v1.endpoints.motion already captured at its own import time
# — test_admin.py/test_sandbox.py call get_settings.cache_clear() during test execution,
# which would otherwise make an in-function get_settings() call fetch a *different* instance
# than the one the endpoint module actually reads, silently no-op'ing a monkeypatch.
settings = get_settings()

VALID_VECTOR_SCENE_REPLY = (
    '```vector-scene\n'
    '{"objects": [{"props": {"object_type": "CIRCLE", "cx": 50, "cy": 50, "r": 20, "fill": "#ff0000"}, "z_index": 0}]}\n'
    '```'
)

VALID_KEYFRAMES_REPLY = (
    '```animation-keyframes\n'
    '{"keyframes": ['
    '{"object_index": 0, "time_ms": 0, "prop": "cx", "value": 50, "easing": "LINEAR"}, '
    '{"object_index": 0, "time_ms": 1000, "prop": "cx", "value": 300, "easing": "LINEAR"}'
    ']}\n'
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


def _create_animation(client, headers):
    _use_mock(MockProvider(reply=VALID_VECTOR_SCENE_REPLY))
    try:
        doc = client.post("/api/v1/vector/documents", json={"prompt": "a red circle"}, headers=headers).json()
    finally:
        _clear_mock()

    _use_mock(MockProvider(reply=VALID_KEYFRAMES_REPLY))
    try:
        anim = client.post(
            "/api/v1/animation/documents",
            json={"vector_document_id": doc["id"], "prompt": "move it", "duration_ms": 1000},
            headers=headers,
        ).json()
    finally:
        _clear_mock()
    return anim


def _create_project(client, headers, total_duration_ms=3000):
    return client.post(
        "/api/v1/motion/projects",
        json={"title": "test project", "canvas_width": 400, "canvas_height": 400, "total_duration_ms": total_duration_ms},
        headers=headers,
    ).json()


def test_create_motion_project(client, db_session):
    token = _register_and_login(client, "motion-create@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    project = _create_project(client, headers)
    assert project["title"] == "test project"
    assert project["total_duration_ms"] == 3000
    assert project["loop"] is False


def test_add_clip_requires_owned_animation(client, db_session):
    token_a = _register_and_login(client, "motion-clip-owner@example.com")
    token_b = _register_and_login(client, "motion-clip-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    anim = _create_animation(client, headers_a)
    project = _create_project(client, headers_b)

    resp = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim["id"]},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_add_clip_rejects_clip_exceeding_project_duration(client, db_session):
    token = _register_and_login(client, "motion-toolong@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    anim = _create_animation(client, headers)  # duration_ms = 1000
    project = _create_project(client, headers, total_duration_ms=500)

    resp = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim["id"], "start_offset_ms": 0},
        headers=headers,
    )
    assert resp.status_code == 400


def test_clip_count_is_capped(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "motion_max_clips", 1)

    token = _register_and_login(client, "motion-cap@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    anim1 = _create_animation(client, headers)
    anim2 = _create_animation(client, headers)
    project = _create_project(client, headers, total_duration_ms=5000)

    first = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim1["id"]},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim2["id"]},
        headers=headers,
    )
    assert second.status_code == 400


def test_manual_clip_crud(client, db_session):
    token = _register_and_login(client, "motion-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    anim = _create_animation(client, headers)
    project = _create_project(client, headers, total_duration_ms=3000)

    added = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim["id"], "start_offset_ms": 500, "x_offset": 10, "y_offset": 20},
        headers=headers,
    )
    assert added.status_code == 201
    clip_id = added.json()["id"]
    assert added.json()["start_offset_ms"] == 500

    patched = client.patch(
        f"/api/v1/motion/projects/{project['id']}/clips/{clip_id}",
        json={"x_offset": 99},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["x_offset"] == 99

    deleted = client.delete(f"/api/v1/motion/projects/{project['id']}/clips/{clip_id}", headers=headers)
    assert deleted.status_code == 204


def test_export_produces_namespaced_keyframe_rules_for_each_clip(client, db_session):
    token = _register_and_login(client, "motion-export@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    anim1 = _create_animation(client, headers)
    anim2 = _create_animation(client, headers)
    project = _create_project(client, headers, total_duration_ms=3000)

    clip1 = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim1["id"], "start_offset_ms": 0, "x_offset": 0},
        headers=headers,
    ).json()
    clip2 = client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim2["id"], "start_offset_ms": 1000, "x_offset": 200},
        headers=headers,
    ).json()

    resp = client.get(f"/api/v1/motion/projects/{project['id']}/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert f"clip-{clip1['id']}" in resp.text
    assert f"clip-{clip2['id']}" in resp.text
    assert 'translate(0,0)' in resp.text
    assert 'translate(200,0)' in resp.text


def test_export_synthesizes_hold_stops_for_a_clip_not_spanning_full_duration(client, db_session):
    token = _register_and_login(client, "motion-hold@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    anim = _create_animation(client, headers)  # keyframes at 0ms and 1000ms, duration 1000ms
    project = _create_project(client, headers, total_duration_ms=3000)

    client.post(
        f"/api/v1/motion/projects/{project['id']}/clips",
        json={"animation_document_id": anim["id"], "start_offset_ms": 1000},
        headers=headers,
    )

    resp = client.get(f"/api/v1/motion/projects/{project['id']}/export", headers=headers)
    assert resp.status_code == 200
    # The clip's own keyframes land at 1000ms/3000ms=33.333% and 2000ms/3000ms=66.667% of the
    # project timeline, so an explicit 0% hold stop (at the first keyframe's value) and a 100%
    # hold stop (at the last keyframe's value) must be synthesized — four stops total, not two.
    # (Percentage formatting mirrors Animator's own float rendering, e.g. "100.0%", so this
    # checks the declarations rather than assuming clean integer percentage strings.)
    style_start = resp.text.index("<style>")
    style_end = resp.text.index("</style>")
    style_block = resp.text[style_start:style_end]
    assert style_block.count("cx:") == 4
    assert "cx: 50" in style_block
    assert "cx: 300" in style_block


def test_motion_project_isolated_per_user(client, db_session):
    token_a = _register_and_login(client, "motion-owner@example.com")
    token_b = _register_and_login(client, "motion-intruder@example.com")
    project = _create_project(client, {"Authorization": f"Bearer {token_a}"})

    forbidden = client.get(
        f"/api/v1/motion/projects/{project['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden.status_code == 404
