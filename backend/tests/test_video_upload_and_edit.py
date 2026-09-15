import io

from app.services.video_edit_service import launch_video_edit_job

_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32  # not a real playable MP4, just non-empty bytes


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _upload_video(client, headers):
    return client.post(
        "/api/v1/videos", headers=headers, files={"file": ("clip.mp4", io.BytesIO(_MP4_BYTES), "video/mp4")}
    )


# --- upload ------------------------------------------------------------------------------


def test_upload_video_rejects_unsupported_type(client):
    token = _register_and_login(client, "video-upload-bad-type@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/videos", headers=headers, files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}
    )
    assert resp.status_code == 415


def test_upload_video_rejects_empty_file(client):
    token = _register_and_login(client, "video-upload-empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/videos", headers=headers, files={"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")})
    assert resp.status_code == 400


def test_upload_video_succeeds_with_null_metadata(client):
    token = _register_and_login(client, "video-upload-ok@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = _upload_video(client, headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["content_type"] == "video/mp4"
    assert body["size_bytes"] == len(_MP4_BYTES)
    # width/height/duration_seconds are unknown for an uploaded (not generated) video.
    assert body["width"] is None
    assert body["height"] is None
    assert body["duration_seconds"] is None


def test_uploaded_video_isolated_between_users(client):
    token_a = _register_and_login(client, "video-owner@example.com")
    token_b = _register_and_login(client, "video-intruder@example.com")
    uploaded = _upload_video(client, {"Authorization": f"Bearer {token_a}"})
    video_id = uploaded.json()["id"]

    forbidden = client.get(f"/api/v1/videos/{video_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404
    forbidden_delete = client.delete(f"/api/v1/videos/{video_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden_delete.status_code == 404


# --- video-edit endpoint -------------------------------------------------------------------


def test_video_edit_job_created_returns_pending(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_video_id": video["id"]},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["operation"] == "REMOVE_BACKGROUND"
    assert body["background_color"]  # defaulted from settings


def test_video_edit_rejects_other_users_source_video(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "video-edit-owner@example.com")
    token_b = _register_and_login(client, "video-edit-intruder@example.com")
    video = _upload_video(client, {"Authorization": f"Bearer {token_a}"}).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_video_id": video["id"]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_video_edit_job_isolated_per_user(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-list@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()
    created = client.post(
        "/api/v1/video-edit", json={"operation": "REMOVE_BACKGROUND", "source_video_id": video["id"]}, headers=headers
    )
    job_id = created.json()["id"]

    other_token = _register_and_login(client, "video-edit-other@example.com")
    forbidden = client.get(f"/api/v1/video-edit/{job_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert forbidden.status_code == 404


def test_video_edit_cancel_requires_pending_or_running(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-cancel@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()
    created = client.post(
        "/api/v1/video-edit", json={"operation": "REMOVE_BACKGROUND", "source_video_id": video["id"]}, headers=headers
    )
    job_id = created.json()["id"]

    first = client.post(f"/api/v1/video-edit/{job_id}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = client.post(f"/api/v1/video-edit/{job_id}/cancel", headers=headers)
    assert second.status_code == 400


def test_launch_video_edit_job_spawns_a_real_separate_process():
    # No video/.venv provisioned here, so this falls back to the backend's own interpreter
    # running video/scripts/edit_video.py, which has SQLAlchemy but not imageio/rembg. Same
    # tolerance as the equivalent generate.py subprocess-spawn test.
    proc = launch_video_edit_job(
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
        "REMOVE_BACKGROUND",
        "/tmp/does-not-matter.mp4",
        "#00b140",
    )
    assert proc.pid is not None
    proc.wait(timeout=30)
