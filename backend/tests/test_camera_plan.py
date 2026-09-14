from app.db.models.camera_plan import CameraPlan
from app.main import app
from app.services.camera_plan_service import describe_camera_plan
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


def _create_storyboard_shot(client, headers):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply=VALID_STORYBOARD_REPLY)
    try:
        resp = client.post("/api/v1/storyboards", json={"script": "scene"}, headers=headers)
        return resp.json()["shots"][0]["id"]
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


# --- camera_plan_service ----------------------------------------------------------------


def test_describe_camera_plan_static_minimal():
    plan = CameraPlan(motion_type="STATIC")
    assert describe_camera_plan(plan) == "a static, locked-off shot"


def test_describe_camera_plan_includes_lens_and_settings():
    plan = CameraPlan(
        motion_type="DOLLY_IN",
        lens="50mm prime",
        focal_length_mm=50,
        aperture=1.8,
        shutter_speed="1/48",
        depth_of_field="shallow",
        motion_path="moves toward the subject's face",
    )
    description = describe_camera_plan(plan)
    assert "dolly-in" in description
    assert "50mm prime" in description
    assert "50mm" in description
    assert "f/1.8" in description
    assert "shutter 1/48" in description
    assert "shallow depth of field" in description
    assert "moves toward the subject's face" in description


def test_describe_camera_plan_unknown_motion_type_falls_back_to_lowercase():
    plan = CameraPlan(motion_type="ORBIT")
    assert describe_camera_plan(plan).startswith("an orbiting shot")


# --- camera-plans endpoint -----------------------------------------------------------------


def test_camera_plan_crud(client):
    token = _register_and_login(client, "camera-plan-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/camera-plans", json={"name": "Opening shot", "motion_type": "PUSH_IN", "lens": "35mm"}, headers=headers
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]
    assert created.json()["motion_type"] == "PUSH_IN"

    listed = client.get("/api/v1/camera-plans", headers=headers)
    assert len(listed.json()) == 1

    patched = client.patch(f"/api/v1/camera-plans/{plan_id}", json={"aperture": 2.8}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["aperture"] == 2.8

    deleted = client.delete(f"/api/v1/camera-plans/{plan_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/camera-plans/{plan_id}", headers=headers).status_code == 404


def test_camera_plan_rejects_invalid_motion_type(client):
    token = _register_and_login(client, "camera-plan-invalid@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/camera-plans", json={"motion_type": "TELEPORT"}, headers=headers)
    assert resp.status_code == 422


def test_camera_plan_can_link_to_owned_storyboard_shot(client):
    token = _register_and_login(client, "camera-plan-shot@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    shot_id = _create_storyboard_shot(client, headers)

    created = client.post(
        "/api/v1/camera-plans", json={"storyboard_shot_id": shot_id, "motion_type": "TRACKING"}, headers=headers
    )
    assert created.status_code == 201
    assert created.json()["storyboard_shot_id"] == shot_id


def test_camera_plan_rejects_other_users_storyboard_shot(client):
    token_a = _register_and_login(client, "camera-plan-shot-owner@example.com")
    token_b = _register_and_login(client, "camera-plan-shot-borrower@example.com")
    shot_id = _create_storyboard_shot(client, {"Authorization": f"Bearer {token_a}"})

    resp = client.post(
        "/api/v1/camera-plans",
        json={"storyboard_shot_id": shot_id, "motion_type": "STATIC"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_camera_plan_isolated_between_users(client):
    token_a = _register_and_login(client, "camera-plan-owner@example.com")
    token_b = _register_and_login(client, "camera-plan-intruder@example.com")
    created = client.post(
        "/api/v1/camera-plans", json={"motion_type": "STATIC"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    plan_id = created.json()["id"]

    forbidden = client.get(f"/api/v1/camera-plans/{plan_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404
