from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_STORYBOARD_REPLY = (
    '```storyboard\n'
    '{"shots": [{"scene_id": "1", "duration_seconds": 4.0, "camera": "medium shot", "lens": null, '
    '"composition": null, "characters": ["Ava"], "action": "Ava walks in.", "environment": "hallway", '
    '"lighting": null, "dialogue": null, "sound": null, "vfx": null, '
    '"generation_prompt": "Ava walks into a hallway"}, '
    '{"scene_id": "2", "duration_seconds": 3.0, "camera": "close-up", "lens": null, "composition": null, '
    '"characters": ["Ava"], "action": "Ava smiles.", "environment": "hallway", "lighting": null, '
    '"dialogue": null, "sound": null, "vfx": null, "generation_prompt": "Close-up of Ava smiling"}]}\n'
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


def test_create_film_generates_script_storyboard_and_video_jobs(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["Ava walks down a quiet hallway and smiles.", VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "director-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/director/films",
            json={"idea": "A woman comes home after a long day.", "title": "Homecoming"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Homecoming"
        assert body["script"] == "Ava walks down a quiet hallway and smiles."
        assert len(body["shots"]) == 2
        for shot in body["shots"]:
            assert shot["video_generation_job_id"] is not None
    finally:
        _clear_mock()


def test_create_film_without_video_generation(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["a short script", VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "director-no-video@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/director/films",
            json={"idea": "A short idea.", "generate_video": False},
            headers=headers,
        )
        assert resp.status_code == 201
        for shot in resp.json()["shots"]:
            assert shot["video_generation_job_id"] is None
    finally:
        _clear_mock()


def test_create_film_defaults_title_when_none_given(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["script", VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "director-default-title@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/director/films", json={"idea": "idea", "generate_video": False}, headers=headers)
        assert resp.json()["title"] == "Untitled film"
    finally:
        _clear_mock()


def test_create_film_includes_character_and_world_guidance(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["script", VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "director-consistency@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        character = client.post(
            "/api/v1/characters", json={"name": "Ava", "appearance": "tall, red coat"}, headers=headers
        ).json()
        world = client.post(
            "/api/v1/world-bibles", json={"name": "Neo Tokyo", "atmosphere": "rainy"}, headers=headers
        ).json()

        resp = client.post(
            "/api/v1/director/films",
            json={
                "idea": "idea",
                "generate_video": False,
                "character_ids": [character["id"]],
                "world_bible_id": world["id"],
            },
            headers=headers,
        )
        assert resp.status_code == 201

        system_message = next(m for m in mock.last_messages if m["role"] == "system")
        assert "Ava" in system_message["content"]
        assert "rainy" in system_message["content"]
    finally:
        _clear_mock()


def test_create_film_rejects_other_users_character(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["script", VALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token_a = _register_and_login(client, "director-char-owner@example.com")
        token_b = _register_and_login(client, "director-char-borrower@example.com")
        character = client.post(
            "/api/v1/characters", json={"name": "Ava"}, headers={"Authorization": f"Bearer {token_a}"}
        ).json()

        resp = client.post(
            "/api/v1/director/films",
            json={"idea": "idea", "character_ids": [character["id"]]},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404
    finally:
        _clear_mock()


def test_create_film_fails_with_502_when_storyboard_generation_fails(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.director.launch_video_generation_job", lambda *a, **k: None)
    mock = MockProvider(replies=["script", INVALID_STORYBOARD_REPLY])
    _use_mock(mock)
    try:
        token = _register_and_login(client, "director-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/director/films", json={"idea": "idea"}, headers=headers)
        assert resp.status_code == 502
    finally:
        _clear_mock()
