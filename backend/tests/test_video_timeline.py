import io

from app.services.video_timeline_export_service import launch_timeline_export_job

_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32  # not a real playable MP4, just non-empty bytes


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _upload_video(client, headers):
    return client.post(
        "/api/v1/videos", headers=headers, files={"file": ("clip.mp4", io.BytesIO(_MP4_BYTES), "video/mp4")}
    ).json()["id"]


def _no_launch(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_timelines.launch_timeline_export_job", lambda *a, **k: None)


# --- timeline CRUD ---------------------------------------------------------------------------


def test_create_list_get_delete_timeline(client):
    token = _register_and_login(client, "timeline-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/v1/video-timelines", json={"title": "My Edit"}, headers=headers)
    assert created.status_code == 201
    timeline_id = created.json()["id"]
    assert created.json()["title"] == "My Edit"

    listed = client.get("/api/v1/video-timelines", headers=headers)
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/v1/video-timelines/{timeline_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["clips"] == []

    deleted = client.delete(f"/api/v1/video-timelines/{timeline_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/video-timelines/{timeline_id}", headers=headers).status_code == 404


def test_timeline_isolated_between_users(client):
    token_a = _register_and_login(client, "timeline-owner@example.com")
    token_b = _register_and_login(client, "timeline-intruder@example.com")
    created = client.post(
        "/api/v1/video-timelines", json={"title": "private"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    timeline_id = created.json()["id"]

    forbidden = client.get(f"/api/v1/video-timelines/{timeline_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


# --- clips -------------------------------------------------------------------------------------


def test_add_and_delete_clip(client):
    token = _register_and_login(client, "timeline-clips@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers).json()["id"]
    video_id = _upload_video(client, headers)

    added = client.post(
        f"/api/v1/video-timelines/{timeline_id}/clips",
        json={"video_id": video_id, "trim_start_seconds": 1.5, "trim_end_seconds": 4.0},
        headers=headers,
    )
    assert added.status_code == 201
    clip = added.json()
    assert clip["video_id"] == video_id
    assert clip["clip_index"] == 0
    assert clip["trim_start_seconds"] == 1.5

    detail = client.get(f"/api/v1/video-timelines/{timeline_id}", headers=headers)
    assert len(detail.json()["clips"]) == 1

    deleted = client.delete(f"/api/v1/video-timelines/{timeline_id}/clips/{clip['id']}", headers=headers)
    assert deleted.status_code == 204
    detail2 = client.get(f"/api/v1/video-timelines/{timeline_id}", headers=headers)
    assert detail2.json()["clips"] == []


def test_add_clips_increments_clip_index(client):
    token = _register_and_login(client, "timeline-clip-index@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers).json()["id"]
    video_a = _upload_video(client, headers)
    video_b = _upload_video(client, headers)

    first = client.post(
        f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": video_a}, headers=headers
    ).json()
    second = client.post(
        f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": video_b}, headers=headers
    ).json()
    assert first["clip_index"] == 0
    assert second["clip_index"] == 1


def test_add_clip_rejects_other_users_video(client):
    token_a = _register_and_login(client, "timeline-clip-owner@example.com")
    token_b = _register_and_login(client, "timeline-clip-borrower@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers_a).json()["id"]
    other_video_id = _upload_video(client, headers_b)

    resp = client.post(
        f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": other_video_id}, headers=headers_a
    )
    assert resp.status_code == 404


# --- export --------------------------------------------------------------------------------


def test_export_rejects_empty_timeline(client):
    token = _register_and_login(client, "timeline-export-empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers).json()["id"]

    resp = client.post(f"/api/v1/video-timelines/{timeline_id}/export", headers=headers)
    assert resp.status_code == 400


def test_export_creates_job(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "timeline-export-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers).json()["id"]
    video_id = _upload_video(client, headers)
    client.post(f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": video_id}, headers=headers)

    resp = client.post(f"/api/v1/video-timelines/{timeline_id}/export", headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["timeline_id"] == timeline_id


def test_export_job_isolated_between_users(client, monkeypatch):
    _no_launch(monkeypatch)
    token_a = _register_and_login(client, "timeline-export-owner@example.com")
    token_b = _register_and_login(client, "timeline-export-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers_a).json()["id"]
    video_id = _upload_video(client, headers_a)
    client.post(f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": video_id}, headers=headers_a)
    job_id = client.post(f"/api/v1/video-timelines/{timeline_id}/export", headers=headers_a).json()["id"]

    forbidden = client.get(
        f"/api/v1/video-timelines/exports/{job_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden.status_code == 404


def test_export_cancel_requires_pending_or_running(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "timeline-export-cancel@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    timeline_id = client.post("/api/v1/video-timelines", json={"title": "t"}, headers=headers).json()["id"]
    video_id = _upload_video(client, headers)
    client.post(f"/api/v1/video-timelines/{timeline_id}/clips", json={"video_id": video_id}, headers=headers)
    job_id = client.post(f"/api/v1/video-timelines/{timeline_id}/export", headers=headers).json()["id"]

    first = client.post(f"/api/v1/video-timelines/exports/{job_id}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = client.post(f"/api/v1/video-timelines/exports/{job_id}/cancel", headers=headers)
    assert second.status_code == 400


def test_launch_timeline_export_job_spawns_a_real_separate_process():
    # No video/.venv provisioned here, so this falls back to the backend's own interpreter
    # running video/scripts/export_timeline.py, which has SQLAlchemy but not imageio. Same
    # tolerance as the equivalent generate.py/edit_video.py subprocess-spawn tests.
    proc = launch_timeline_export_job(
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
        [{"storage_path": "/tmp/does-not-matter.mp4", "trim_start_seconds": 0.0, "trim_end_seconds": None}],
    )
    assert proc.pid is not None
    proc.wait(timeout=30)
