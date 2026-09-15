import io
import os

from app.services.video_edit_service import launch_video_edit_job

_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32  # not a real playable MP4, just non-empty bytes
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _upload_video(client, headers):
    return client.post(
        "/api/v1/videos", headers=headers, files={"file": ("clip.mp4", io.BytesIO(_MP4_BYTES), "video/mp4")}
    )


def _upload_mask_image(client, headers):
    return client.post(
        "/api/v1/images", headers=headers, files={"file": ("mask.png", io.BytesIO(_PNG_BYTES), "image/png")}
    ).json()["id"]


def _upload_image(client, headers, filename="bg.png"):
    return client.post(
        "/api/v1/images", headers=headers, files={"file": (filename, io.BytesIO(_PNG_BYTES), "image/png")}
    ).json()["id"]


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


# --- REMOVE_OBJECT ---------------------------------------------------------------------------


def test_remove_object_requires_mask_and_prompt(client):
    token = _register_and_login(client, "video-edit-object-missing@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "REMOVE_OBJECT", "source_video_id": video["id"]},
        headers=headers,
    )
    assert resp.status_code == 422


def test_remove_object_job_created_with_mask_and_prompt(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-object-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()
    mask_id = _upload_mask_image(client, headers)

    resp = client.post(
        "/api/v1/video-edit",
        json={
            "operation": "REMOVE_OBJECT",
            "source_video_id": video["id"],
            "mask_image_id": mask_id,
            "prompt": "empty street",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "REMOVE_OBJECT"
    assert body["mask_image_id"] == mask_id
    assert body["prompt"] == "empty street"
    assert body["steps"] > 0


def test_remove_object_rejects_other_users_mask_image(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "video-edit-mask-owner@example.com")
    token_b = _register_and_login(client, "video-edit-mask-borrower@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    video = _upload_video(client, headers_a).json()
    other_mask_id = _upload_mask_image(client, headers_b)

    resp = client.post(
        "/api/v1/video-edit",
        json={
            "operation": "REMOVE_OBJECT",
            "source_video_id": video["id"],
            "mask_image_id": other_mask_id,
            "prompt": "empty street",
        },
        headers=headers_a,
    )
    assert resp.status_code == 404


# --- REPLACE_ENVIRONMENT --------------------------------------------------------------------


def test_replace_environment_requires_background_image(client):
    token = _register_and_login(client, "video-edit-env-missing@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "REPLACE_ENVIRONMENT", "source_video_id": video["id"]},
        headers=headers,
    )
    assert resp.status_code == 422


def test_replace_environment_job_created_with_background_image(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-env-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()
    background_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/video-edit",
        json={
            "operation": "REPLACE_ENVIRONMENT",
            "source_video_id": video["id"],
            "background_image_id": background_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "REPLACE_ENVIRONMENT"
    assert body["background_image_id"] == background_id


def test_replace_environment_rejects_other_users_background_image(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "video-edit-env-owner@example.com")
    token_b = _register_and_login(client, "video-edit-env-borrower@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    video = _upload_video(client, headers_a).json()
    other_background_id = _upload_image(client, headers_b)

    resp = client.post(
        "/api/v1/video-edit",
        json={
            "operation": "REPLACE_ENVIRONMENT",
            "source_video_id": video["id"],
            "background_image_id": other_background_id,
        },
        headers=headers_a,
    )
    assert resp.status_code == 404


# --- COLOR_GRADE -----------------------------------------------------------------------------


def test_color_grade_requires_preset(client):
    token = _register_and_login(client, "video-edit-grade-missing@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit", json={"operation": "COLOR_GRADE", "source_video_id": video["id"]}, headers=headers
    )
    assert resp.status_code == 422


def test_color_grade_rejects_unknown_preset(client):
    token = _register_and_login(client, "video-edit-grade-unknown@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "COLOR_GRADE", "source_video_id": video["id"], "color_preset": "SEPIA_DELUXE"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_color_grade_job_created_with_preset(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-grade-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "COLOR_GRADE", "source_video_id": video["id"], "color_preset": "CINEMATIC"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "COLOR_GRADE"
    assert body["color_preset"] == "CINEMATIC"


def test_color_grade_presets_match_between_backend_and_subprocess():
    """The Literal in the schema and the _COLOR_GRADE_PRESETS dict in the subprocess script
    are deliberately duplicated (separate Python environments) rather than shared — this test
    is the guardrail that keeps them from silently drifting apart."""
    import re

    from app.schemas.video_edit import ColorGradePreset

    schema_presets = set(ColorGradePreset.__args__)

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "video", "scripts", "edit_video.py")
    with open(script_path, encoding="utf-8") as f:
        script_source = f.read()
    match = re.search(r"_COLOR_GRADE_PRESETS = \{(.*?)\n\}", script_source, re.DOTALL)
    assert match is not None
    script_presets = set(re.findall(r'"([A-Z_]+)":\s*\{', match.group(1)))

    assert schema_presets == script_presets


# --- ADD_VFX -----------------------------------------------------------------------------


def test_add_vfx_requires_vfx_type(client):
    token = _register_and_login(client, "video-edit-vfx-missing@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit", json={"operation": "ADD_VFX", "source_video_id": video["id"]}, headers=headers
    )
    assert resp.status_code == 422


def test_add_vfx_rejects_unknown_vfx_type(client):
    token = _register_and_login(client, "video-edit-vfx-unknown@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "ADD_VFX", "source_video_id": video["id"], "vfx_type": "LASER_BEAMS"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_add_vfx_job_created_with_vfx_type(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.video_edit.launch_video_edit_job", lambda *a, **k: None)
    token = _register_and_login(client, "video-edit-vfx-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    video = _upload_video(client, headers).json()

    resp = client.post(
        "/api/v1/video-edit",
        json={"operation": "ADD_VFX", "source_video_id": video["id"], "vfx_type": "RAIN"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["operation"] == "ADD_VFX"
    assert body["vfx_type"] == "RAIN"


def test_vfx_presets_match_between_backend_and_subprocess():
    """Same guardrail pattern as test_color_grade_presets_match_between_backend_and_subprocess
    — the VfxType Literal and _VFX_PARTICLE_PRESETS dict are deliberately duplicated across
    the two separate Python environments."""
    import re

    from app.schemas.video_edit import VfxType

    schema_presets = set(VfxType.__args__)

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "video", "scripts", "edit_video.py")
    with open(script_path, encoding="utf-8") as f:
        script_source = f.read()
    match = re.search(r"_VFX_PARTICLE_PRESETS = \{(.*?)\n\}", script_source, re.DOTALL)
    assert match is not None
    script_presets = set(re.findall(r'"([A-Z_]+)":\s*\{', match.group(1)))

    assert schema_presets == script_presets
