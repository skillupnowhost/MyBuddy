from app.services.model_3d_generation_service import launch_model_3d_generation_job


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_text_to_3d_job_created_returns_pending(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)

    token = _register_and_login(client, "cg3d-text-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/model3d-generation", json={"prompt": "a low-poly red sports car"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["prompt"] == "a low-poly red sports car"
    assert body["source_image_id"] is None


def test_rejects_when_neither_prompt_nor_image_given(client):
    token = _register_and_login(client, "cg3d-neither@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/model3d-generation", json={}, headers=headers)
    assert resp.status_code == 422


def test_image_to_3d_requires_owned_source_image(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "cg3d-badimage@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/model3d-generation",
        json={"source_image_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_rejects_steps_over_cap(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "cg3d-manysteps@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/model3d-generation", json={"prompt": "slow", "steps": 99999}, headers=headers)
    assert resp.status_code == 400


def test_job_isolated_per_user(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    token_a = _register_and_login(client, "cg3d-owner@example.com")
    token_b = _register_and_login(client, "cg3d-intruder@example.com")

    resp = client.post(
        "/api/v1/model3d-generation", json={"prompt": "mine"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    job_id = resp.json()["id"]

    forbidden = client.get(f"/api/v1/model3d-generation/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


def test_cancel_requires_pending_or_running(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.model_3d_generation.launch_model_3d_generation_job", lambda *a, **k: None)
    token = _register_and_login(client, "cg3d-cancel@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/model3d-generation", json={"prompt": "cancel me"}, headers=headers)
    job_id = resp.json()["id"]

    first = client.post(f"/api/v1/model3d-generation/{job_id}/cancel", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"

    second = client.post(f"/api/v1/model3d-generation/{job_id}/cancel", headers=headers)
    assert second.status_code == 400


def test_model_3d_not_found_for_other_user(client):
    token_a = _register_and_login(client, "model3d-owner@example.com")
    resp = client.get(
        "/api/v1/models3d/00000000-0000-0000-0000-000000000000", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 404


def test_launch_model_3d_generation_job_spawns_a_real_separate_process():
    # No cg3d/.venv provisioned here, so this falls back to the backend's own interpreter
    # running cg3d/scripts/generate.py, which has SQLAlchemy but not torch/diffusers. Same
    # tolerance as the equivalent imagegen/video subprocess-spawn tests — what matters is a
    # genuine child process starts and exits on its own rather than hanging.
    proc = launch_model_3d_generation_job(
        "00000000-0000-0000-0000-000000000000",
        "00000000-0000-0000-0000-000000000000",
        "smoke test prompt",
        None,
        64,
        15.0,
        None,
    )
    assert proc.pid is not None
    proc.wait(timeout=30)
