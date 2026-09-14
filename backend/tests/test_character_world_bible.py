from app.db.models.character import Character
from app.db.models.world_bible import WorldBible
from app.main import app
from app.services.consistency_service import character_guidance, world_guidance
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_STORYBOARD_REPLY = (
    '```storyboard\n'
    '{"shots": [{"scene_id": "1", "duration_seconds": 4.0, "camera": "medium shot", "lens": null, '
    '"composition": null, "characters": ["Ava"], "action": "Ava walks in.", "environment": "hallway", '
    '"lighting": null, "dialogue": null, "sound": null, "vfx": null, '
    '"generation_prompt": "Ava walks into a hallway"}]}\n'
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


# --- consistency_service ----------------------------------------------------------------


def test_character_guidance_empty_for_no_characters():
    assert character_guidance([]) == ""


def test_character_guidance_includes_name_appearance_personality():
    character = Character(name="Ava", appearance="tall, red coat", personality="determined")
    guidance = character_guidance([character])
    assert "Ava" in guidance
    assert "tall, red coat" in guidance
    assert "determined" in guidance


def test_character_guidance_handles_missing_details():
    character = Character(name="Bo")
    guidance = character_guidance([character])
    assert guidance == "Characters in this story, keep their appearance and personality consistent across shots: Bo."


def test_world_guidance_empty_for_none():
    assert world_guidance(None) == ""


def test_world_guidance_includes_all_set_fields():
    world = WorldBible(
        name="Neo Tokyo",
        setting_description="rain-soaked megacity",
        atmosphere="perpetual night",
        visual_style="neon noir",
        color_palette="cyan and magenta",
        rules="no daylight scenes",
    )
    guidance = world_guidance(world)
    assert "rain-soaked megacity" in guidance
    assert "perpetual night" in guidance
    assert "neon noir" in guidance
    assert "cyan and magenta" in guidance
    assert "no daylight scenes" in guidance


# --- characters endpoint -------------------------------------------------------------------


def test_character_crud(client):
    token = _register_and_login(client, "character-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/characters", json={"name": "Ava", "appearance": "tall, red coat"}, headers=headers
    )
    assert created.status_code == 201
    character_id = created.json()["id"]

    listed = client.get("/api/v1/characters", headers=headers)
    assert len(listed.json()) == 1

    patched = client.patch(f"/api/v1/characters/{character_id}", json={"personality": "brave"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["personality"] == "brave"

    deleted = client.delete(f"/api/v1/characters/{character_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/characters/{character_id}", headers=headers).status_code == 404


def test_character_isolated_between_users(client):
    token_a = _register_and_login(client, "character-owner@example.com")
    token_b = _register_and_login(client, "character-intruder@example.com")
    created = client.post(
        "/api/v1/characters", json={"name": "private"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    character_id = created.json()["id"]

    forbidden = client.get(f"/api/v1/characters/{character_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


# --- world-bibles endpoint -----------------------------------------------------------------


def test_world_bible_crud(client):
    token = _register_and_login(client, "world-bible-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/v1/world-bibles", json={"name": "Neo Tokyo", "atmosphere": "rainy"}, headers=headers)
    assert created.status_code == 201
    world_bible_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/world-bibles/{world_bible_id}", json={"visual_style": "neon noir"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["visual_style"] == "neon noir"

    deleted = client.delete(f"/api/v1/world-bibles/{world_bible_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/world-bibles/{world_bible_id}", headers=headers).status_code == 404


def test_world_bible_isolated_between_users(client):
    token_a = _register_and_login(client, "world-bible-owner@example.com")
    token_b = _register_and_login(client, "world-bible-intruder@example.com")
    created = client.post(
        "/api/v1/world-bibles", json={"name": "private"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    world_bible_id = created.json()["id"]

    forbidden = client.get(
        f"/api/v1/world-bibles/{world_bible_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden.status_code == 404


# --- storyboard integration: guidance actually reaches the model --------------------------


def test_storyboard_generation_includes_character_and_world_guidance(client):
    mock = MockProvider(reply=VALID_STORYBOARD_REPLY)
    _use_mock(mock)
    try:
        token = _register_and_login(client, "storyboard-consistency@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        character = client.post(
            "/api/v1/characters", json={"name": "Ava", "appearance": "tall, red coat"}, headers=headers
        ).json()
        world = client.post(
            "/api/v1/world-bibles", json={"name": "Neo Tokyo", "atmosphere": "rainy"}, headers=headers
        ).json()

        resp = client.post(
            "/api/v1/storyboards",
            json={
                "script": "Ava arrives.",
                "character_ids": [character["id"]],
                "world_bible_id": world["id"],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["character_ids"] == [character["id"]]
        assert resp.json()["world_bible_id"] == world["id"]

        system_message = next(m for m in mock.last_messages if m["role"] == "system")
        assert "Ava" in system_message["content"]
        assert "tall, red coat" in system_message["content"]
        assert "rainy" in system_message["content"]
    finally:
        _clear_mock()


def test_storyboard_generation_rejects_other_users_character(client):
    mock = MockProvider(reply=VALID_STORYBOARD_REPLY)
    _use_mock(mock)
    try:
        token_a = _register_and_login(client, "storyboard-char-owner@example.com")
        token_b = _register_and_login(client, "storyboard-char-borrower@example.com")
        character = client.post(
            "/api/v1/characters", json={"name": "Ava"}, headers={"Authorization": f"Bearer {token_a}"}
        ).json()

        resp = client.post(
            "/api/v1/storyboards",
            json={"script": "scene", "character_ids": [character["id"]]},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404
    finally:
        _clear_mock()
