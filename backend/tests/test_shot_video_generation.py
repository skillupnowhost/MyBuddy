from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

VALID_STORYBOARD_REPLY = (
    '```storyboard\n'
    '{"shots": [{"scene_id": "1", "duration_seconds": 4.0, "camera": "medium shot", "lens": null, '
    '"composition": null, "characters": [], "action": "Something happens.", "environment": "room", '
    '"lighting": null, "dialogue": null, "sound": null, "vfx": null, '
    '"generation_prompt": "Something happens in a room"}]}\n'
    '```'
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _create_storyboard(client, headers):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply=VALID_STORYBOARD_REPLY)
    try:
        return client.post("/api/v1/storyboards", json={"script": "scene"}, headers=headers).json()
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_generate_shot_video_creates_job_and_links_shot(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.storyboard.launch_video_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "shot-video-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    storyboard = _create_storyboard(client, headers)
    shot = storyboard["shots"][0]

    resp = client.post(
        f"/api/v1/storyboards/{storyboard['id']}/shots/{shot['id']}/generate-video", json={}, headers=headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["prompt"] == shot["generation_prompt"]

    fetched_storyboard = client.get(f"/api/v1/storyboards/{storyboard['id']}", headers=headers)
    assert fetched_storyboard.json()["shots"][0]["video_generation_job_id"] == body["id"]


def test_generate_shot_video_enriches_prompt_with_camera_plan(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.storyboard.launch_video_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "shot-video-camera@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    storyboard = _create_storyboard(client, headers)
    shot = storyboard["shots"][0]

    camera_plan = client.post(
        "/api/v1/camera-plans", json={"motion_type": "DOLLY_IN", "lens": "50mm"}, headers=headers
    ).json()

    resp = client.post(
        f"/api/v1/storyboards/{storyboard['id']}/shots/{shot['id']}/generate-video",
        json={"camera_plan_id": camera_plan["id"]},
        headers=headers,
    )
    assert resp.status_code == 201
    assert "dolly-in" in resp.json()["prompt"]
    assert "50mm" in resp.json()["prompt"]
    assert shot["generation_prompt"] in resp.json()["prompt"]


def test_generate_shot_video_rejects_other_users_camera_plan(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.storyboard.launch_video_generation_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "shot-video-owner@example.com")
    token_b = _register_and_login(client, "shot-video-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    storyboard = _create_storyboard(client, headers_a)
    shot = storyboard["shots"][0]
    other_camera_plan = client.post("/api/v1/camera-plans", json={"motion_type": "STATIC"}, headers=headers_b).json()

    resp = client.post(
        f"/api/v1/storyboards/{storyboard['id']}/shots/{shot['id']}/generate-video",
        json={"camera_plan_id": other_camera_plan["id"]},
        headers=headers_a,
    )
    assert resp.status_code == 404


def test_generate_shot_video_rejects_dimensions_over_cap(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.storyboard.launch_video_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "shot-video-bigsize@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    storyboard = _create_storyboard(client, headers)
    shot = storyboard["shots"][0]

    resp = client.post(
        f"/api/v1/storyboards/{storyboard['id']}/shots/{shot['id']}/generate-video",
        json={"width": 999999},
        headers=headers,
    )
    assert resp.status_code == 400


def test_generate_shot_video_rejects_other_users_shot(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.storyboard.launch_video_generation_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "shot-video-shot-owner@example.com")
    token_b = _register_and_login(client, "shot-video-shot-intruder@example.com")
    storyboard = _create_storyboard(client, {"Authorization": f"Bearer {token_a}"})
    shot = storyboard["shots"][0]

    resp = client.post(
        f"/api/v1/storyboards/{storyboard['id']}/shots/{shot['id']}/generate-video",
        json={},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
