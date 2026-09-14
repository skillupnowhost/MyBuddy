import pytest

from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_STORYBOARD_REPLY = (
    '```storyboard\n'
    '{"shots": ['
    '{"scene_id": "1", "duration_seconds": 4.0, "camera": "medium shot, static", "lens": "50mm", '
    '"composition": "rule of thirds", "characters": ["Ava"], '
    '"action": "Ava opens the door and steps inside.", "environment": "dim apartment hallway", '
    '"lighting": "warm overhead bulb", "dialogue": null, "sound": "door creak", "vfx": null, '
    '"generation_prompt": "Ava opens a door into a dim, warmly-lit hallway, medium static shot"}, '
    '{"scene_id": "2", "duration_seconds": 3.0, "camera": "close-up", "lens": "85mm", '
    '"composition": "centered", "characters": ["Ava"], "action": "Ava smiles.", '
    '"environment": "hallway", "lighting": "warm", "dialogue": "Finally home.", "sound": null, '
    '"vfx": null, "generation_prompt": "Close-up of Ava smiling in a warmly-lit hallway"}'
    ']}\n'
    '```'
)

INVALID_STORYBOARD_REPLY = "sorry, I cannot help with that."


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _use_mock(mock):
    app.dependency_overrides[get_llm_client] = lambda: mock


def _clear_mock():
    app.dependency_overrides.pop(get_llm_client, None)


def test_generate_storyboard_creates_shots_from_valid_reply(client):
    _use_mock(MockProvider(reply=VALID_STORYBOARD_REPLY))
    try:
        token = _register_and_login(client, "storyboard-gen@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/storyboards",
            json={"title": "Homecoming", "script": "Ava comes home after a long day."},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Homecoming"
        assert len(body["shots"]) == 2
        assert body["shots"][0]["shot_index"] == 0
        assert body["shots"][0]["camera"] == "medium shot, static"
        assert body["shots"][0]["characters"] == ["Ava"]
        assert body["shots"][1]["dialogue"] == "Finally home."
    finally:
        _clear_mock()


def test_generate_storyboard_retries_once_on_invalid_reply_then_succeeds(client):
    mock = MockProvider(replies=[INVALID_STORYBOARD_REPLY, VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "storyboard-retry@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/storyboards", json={"script": "A short scene."}, headers=headers)
        assert resp.status_code == 201
        assert len(resp.json()["shots"]) == 2
    finally:
        _clear_mock()


def test_generate_storyboard_fails_with_502_after_exhausting_retries(client):
    _use_mock(MockProvider(reply=INVALID_STORYBOARD_REPLY))
    try:
        token = _register_and_login(client, "storyboard-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/storyboards", json={"script": "A short scene."}, headers=headers)
        assert resp.status_code == 502
    finally:
        _clear_mock()


def test_default_title_when_none_given(client):
    _use_mock(MockProvider(reply=VALID_STORYBOARD_REPLY))
    try:
        token = _register_and_login(client, "storyboard-default-title@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/storyboards", json={"script": "A short scene."}, headers=headers)
        assert resp.json()["title"] == "Untitled storyboard"
    finally:
        _clear_mock()


def test_list_get_delete_storyboard(client):
    _use_mock(MockProvider(reply=VALID_STORYBOARD_REPLY))
    try:
        token = _register_and_login(client, "storyboard-crud@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/v1/storyboards", json={"script": "scene"}, headers=headers)
        storyboard_id = created.json()["id"]

        listed = client.get("/api/v1/storyboards", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        fetched = client.get(f"/api/v1/storyboards/{storyboard_id}", headers=headers)
        assert fetched.status_code == 200
        assert len(fetched.json()["shots"]) == 2

        deleted = client.delete(f"/api/v1/storyboards/{storyboard_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/storyboards/{storyboard_id}", headers=headers).status_code == 404
    finally:
        _clear_mock()


def test_storyboard_isolated_between_users(client):
    _use_mock(MockProvider(reply=VALID_STORYBOARD_REPLY))
    try:
        token_a = _register_and_login(client, "storyboard-owner@example.com")
        token_b = _register_and_login(client, "storyboard-intruder@example.com")
        created = client.post(
            "/api/v1/storyboards", json={"script": "scene"}, headers={"Authorization": f"Bearer {token_a}"}
        )
        storyboard_id = created.json()["id"]

        forbidden = client.get(
            f"/api/v1/storyboards/{storyboard_id}", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert forbidden.status_code == 404
        forbidden_delete = client.delete(
            f"/api/v1/storyboards/{storyboard_id}", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert forbidden_delete.status_code == 404
    finally:
        _clear_mock()


async def test_generate_storyboard_service_rejects_too_many_shots():
    # Exercised at the service layer directly (not through the endpoint, whose `settings`
    # is captured at module-import time and can't be reliably overridden per-test via
    # monkeypatch+cache_clear — same staleness caveat noted elsewhere in this codebase for
    # module-level `settings = get_settings()`). VALID_STORYBOARD_REPLY has 2 shots.
    from app.services.storyboard_service import StoryboardGenerationError, generate_storyboard

    mock = MockProvider(reply=VALID_STORYBOARD_REPLY)
    with pytest.raises(StoryboardGenerationError, match="too many shots"):
        await generate_storyboard(mock, "some-model", "scene", max_shots=1, max_retries=0)
