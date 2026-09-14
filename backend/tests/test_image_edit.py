import io

from app.services.image_edit_service import launch_image_edit_job

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _upload_image(client, headers, filename="a.png"):
    resp = client.post(
        "/api/v1/images", headers=headers, files={"file": (filename, io.BytesIO(_PNG_BYTES), "image/png")}
    )
    return resp.json()["id"]


def _no_launch(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_edit.launch_image_edit_job", lambda *a, **k: None)


def test_inpaint_job_requires_mask(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-nomask@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "INPAINT", "source_image_id": source_id, "prompt": "a red bicycle"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_inpaint_job_requires_prompt(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-noprompt@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers, "src.png")
    mask_id = _upload_image(client, headers, "mask.png")

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "INPAINT", "source_image_id": source_id, "mask_image_id": mask_id},
        headers=headers,
    )
    assert resp.status_code == 400


def test_inpaint_job_succeeds_with_mask_and_prompt(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-ok@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers, "src.png")
    mask_id = _upload_image(client, headers, "mask.png")

    resp = client.post(
        "/api/v1/image-edit",
        json={
            "operation": "INPAINT",
            "source_image_id": source_id,
            "mask_image_id": mask_id,
            "prompt": "a red bicycle",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "PENDING"


def test_outpaint_job_requires_positive_padding(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-nopad@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "OUTPAINT", "source_image_id": source_id, "prompt": "more sky"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_outpaint_job_rejects_padding_over_cap(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-bigpad@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={
            "operation": "OUTPAINT",
            "source_image_id": source_id,
            "prompt": "more sky",
            "outpaint_top": 999999,
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_outpaint_job_succeeds_with_padding_and_prompt(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-outpaint-ok@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "OUTPAINT", "source_image_id": source_id, "prompt": "more sky", "outpaint_top": 100},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["params"]["outpaint_top"] == 100


def test_remove_background_ignores_prompt_and_mask(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-bg@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_image_id": source_id},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["prompt"] is None
    assert body["mask_image_id"] is None


def test_image_edit_rejects_unowned_source_image(client, monkeypatch):
    _no_launch(monkeypatch)
    token_a = _register_and_login(client, "edit-src-owner@example.com")
    token_b = _register_and_login(client, "edit-src-intruder@example.com")
    source_id = _upload_image(client, {"Authorization": f"Bearer {token_a}"})

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_image_id": source_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_image_edit_rejects_unowned_mask_image(client, monkeypatch):
    _no_launch(monkeypatch)
    token_a = _register_and_login(client, "edit-mask-owner@example.com")
    token_b = _register_and_login(client, "edit-mask-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    source_id = _upload_image(client, headers_b, "src.png")
    someone_elses_mask_id = _upload_image(client, headers_a, "mask.png")

    resp = client.post(
        "/api/v1/image-edit",
        json={
            "operation": "INPAINT",
            "source_image_id": source_id,
            "mask_image_id": someone_elses_mask_id,
            "prompt": "a red bicycle",
        },
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_image_edit_job_isolated_per_user(client, monkeypatch):
    _no_launch(monkeypatch)
    token_a = _register_and_login(client, "edit-job-owner@example.com")
    token_b = _register_and_login(client, "edit-job-intruder@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    source_id = _upload_image(client, headers_a)
    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_image_id": source_id},
        headers=headers_a,
    )
    job_id = resp.json()["id"]

    forbidden = client.get(f"/api/v1/image-edit/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


def test_cancel_requires_pending_or_running(client, monkeypatch):
    _no_launch(monkeypatch)
    token = _register_and_login(client, "edit-cancel@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    source_id = _upload_image(client, headers)

    resp = client.post(
        "/api/v1/image-edit",
        json={"operation": "REMOVE_BACKGROUND", "source_image_id": source_id},
        headers=headers,
    )
    job_id = resp.json()["id"]

    first = client.post(f"/api/v1/image-edit/{job_id}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = client.post(f"/api/v1/image-edit/{job_id}/cancel", headers=headers)
    assert second.status_code == 400


def test_launch_image_edit_job_spawns_a_real_separate_process():
    # No imagegen/.venv provisioned here, so this falls back to the backend's own
    # interpreter running imagegen/scripts/edit_image.py, which has SQLAlchemy but not
    # torch/diffusers/rembg. Same tolerance as the equivalent image-generation test: what
    # matters is that this is a genuine child process that starts and exits on its own.
    proc = launch_image_edit_job(
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
        "REMOVE_BACKGROUND",
        "00000000-0000-0000-0000-000000000000",
        None,
        None,
        None,
        20,
        0,
        0,
        0,
        0,
    )
    assert proc.pid is not None
    proc.wait(timeout=30)
