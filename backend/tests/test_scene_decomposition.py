from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_SCENE_REPLY = (
    '```scene-objects\n'
    '{"objects": [{"label": "neon sign", "prompt": "a glowing pink neon sign, low-poly"}, '
    '{"label": "parked car", "prompt": "a rusty parked car, low-poly"}]}\n'
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


def test_generate_scene_launches_one_job_per_object(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    _use_mock(MockProvider(reply=VALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "scene-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/model3d-generation/scenes",
            json={"description": "a cyberpunk street at night"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body) == 2
        labels = {obj["label"] for obj in body}
        assert labels == {"neon sign", "parked car"}
        for obj in body:
            assert obj["generation_job"]["status"] == "PENDING"
            assert obj["generation_job"]["prompt"]
    finally:
        _clear_mock()


def test_generate_scene_retries_once_on_invalid_reply_then_succeeds(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=[INVALID_SCENE_REPLY, VALID_SCENE_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "scene-retry@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/model3d-generation/scenes", json={"description": "a scene"}, headers=headers)
        assert resp.status_code == 201
        assert len(resp.json()) == 2
    finally:
        _clear_mock()


def test_generate_scene_fails_with_502_after_exhausting_retries(client):
    _use_mock(MockProvider(reply=INVALID_SCENE_REPLY))
    try:
        token = _register_and_login(client, "scene-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/model3d-generation/scenes", json={"description": "a scene"}, headers=headers)
        assert resp.status_code == 502
    finally:
        _clear_mock()


async def test_decompose_scene_service_rejects_too_many_objects():
    from app.services.scene_decomposition_service import SceneDecompositionError, decompose_scene

    mock = MockProvider(reply=VALID_SCENE_REPLY)  # 2 objects
    import pytest

    with pytest.raises(SceneDecompositionError, match="too many objects"):
        await decompose_scene(mock, "some-model", "a scene", max_objects=1, max_retries=0)
