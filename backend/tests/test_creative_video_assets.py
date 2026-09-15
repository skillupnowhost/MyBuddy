import io
import uuid

from app.db.models.model_3d import Model3D
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
_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _create_storyboard(client, headers):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply=VALID_STORYBOARD_REPLY)
    try:
        return client.post("/api/v1/storyboards", json={"script": "scene"}, headers=headers).json()["id"]
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def _upload_video(client, headers):
    return client.post(
        "/api/v1/videos", headers=headers, files={"file": ("clip.mp4", io.BytesIO(_MP4_BYTES), "video/mp4")}
    ).json()["id"]


def _create_model_3d(db_session, user_id):
    model = Model3D(id=uuid.uuid4(), user_id=user_id, storage_path="/tmp/mesh.obj", format="obj", size_bytes=123)
    db_session.add(model)
    db_session.commit()
    return str(model.id)


def test_attach_storyboard_video_and_model3d_assets(client, db_session):
    token = _register_and_login(client, "creative-video-assets@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    from app.db.models.user import User

    user_id = db_session.query(User).filter(User.email == "creative-video-assets@example.com").one().id

    project = client.post("/api/v1/creative/projects", json={"title": "Film assets"}, headers=headers).json()
    storyboard_id = _create_storyboard(client, headers)
    video_id = _upload_video(client, headers)
    model_3d_id = _create_model_3d(db_session, user_id)

    for asset_type, asset_id in [("STORYBOARD", storyboard_id), ("VIDEO", video_id), ("MODEL_3D", model_3d_id)]:
        resp = client.post(
            f"/api/v1/creative/projects/{project['id']}/assets",
            json={"asset_type": asset_type, "asset_id": asset_id},
            headers=headers,
        )
        assert resp.status_code == 201, f"{asset_type} attach failed: {resp.text}"
        assert resp.json()["asset_type"] == asset_type

    detail = client.get(f"/api/v1/creative/projects/{project['id']}", headers=headers)
    assert len(detail.json()["assets"]) == 3


def test_attach_rejects_other_users_video_asset(client):
    token_a = _register_and_login(client, "creative-video-owner@example.com")
    token_b = _register_and_login(client, "creative-video-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    video_id = _upload_video(client, headers_a)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers_b).json()

    resp = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "VIDEO", "asset_id": video_id},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_attach_rejects_other_users_storyboard_asset(client):
    token_a = _register_and_login(client, "creative-storyboard-owner@example.com")
    token_b = _register_and_login(client, "creative-storyboard-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    storyboard_id = _create_storyboard(client, headers_a)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers_b).json()

    resp = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "STORYBOARD", "asset_id": storyboard_id},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_attach_rejects_other_users_model_3d_asset(client, db_session):
    token_a = _register_and_login(client, "creative-model3d-owner@example.com")
    token_b = _register_and_login(client, "creative-model3d-intruder@example.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    from app.db.models.user import User

    owner_id = db_session.query(User).filter(User.email == "creative-model3d-owner@example.com").one().id
    model_3d_id = _create_model_3d(db_session, owner_id)
    project = client.post("/api/v1/creative/projects", json={"title": "P"}, headers=headers_b).json()

    resp = client.post(
        f"/api/v1/creative/projects/{project['id']}/assets",
        json={"asset_type": "MODEL_3D", "asset_id": model_3d_id},
        headers=headers_b,
    )
    assert resp.status_code == 404
