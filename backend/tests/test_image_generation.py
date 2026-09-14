from app.services.image_generation_service import launch_image_generation_job


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_image_generation_job_created_returns_pending(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_generation.launch_image_generation_job", lambda *a, **k: None)

    token = _register_and_login(client, "imagegen-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/image-generation", json={"prompt": "a small red robot"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["prompt"] == "a small red robot"
    assert body["width"] > 0 and body["height"] > 0 and body["steps"] > 0


def test_image_generation_rejects_dimensions_over_cap(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_generation.launch_image_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "imagegen-bigsize@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/image-generation", json={"prompt": "huge", "width": 999999, "height": 512}, headers=headers
    )
    assert resp.status_code == 400


def test_image_generation_rejects_steps_over_cap(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_generation.launch_image_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "imagegen-manysteps@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/image-generation", json={"prompt": "slow", "steps": 999}, headers=headers)
    assert resp.status_code == 400


def test_image_generation_job_isolated_per_user(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_generation.launch_image_generation_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "imagegen-owner@example.com")
    token_b = _register_and_login(client, "imagegen-intruder@example.com")

    resp = client.post(
        "/api/v1/image-generation", json={"prompt": "mine"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    job_id = resp.json()["id"]

    forbidden = client.get(f"/api/v1/image-generation/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404

    forbidden_cancel = client.post(
        f"/api/v1/image-generation/{job_id}/cancel", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden_cancel.status_code == 404


def test_cancel_requires_pending_or_running(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.image_generation.launch_image_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "imagegen-cancel@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/image-generation", json={"prompt": "cancel me"}, headers=headers)
    job_id = resp.json()["id"]

    first = client.post(f"/api/v1/image-generation/{job_id}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = client.post(f"/api/v1/image-generation/{job_id}/cancel", headers=headers)
    assert second.status_code == 400


def test_launch_image_generation_job_spawns_a_real_separate_process():
    # No imagegen/.venv provisioned here, so this falls back to the backend's own
    # interpreter running imagegen/scripts/generate.py, which has SQLAlchemy but not
    # torch/diffusers. Whether it gets far enough to hit that ImportError or fails earlier
    # on the DB connection (no Postgres configured in this test environment either) doesn't
    # matter for this test — same tolerance as
    # test_launch_training_job_spawns_a_real_separate_process. What matters is that this is
    # a genuine child process (proving the subprocess plumbing is real, not mocked) that
    # starts and exits on its own rather than hanging.
    proc = launch_image_generation_job(
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
        "smoke test prompt",
        None,
        512,
        512,
        4,
        None,
    )
    assert proc.pid is not None
    proc.wait(timeout=30)
