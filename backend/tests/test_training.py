import io

from app.core.config import get_settings
from app.services.training_service import launch_training_job


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _valid_jsonl():
    lines = [
        '{"messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]}',
        '{"messages": [{"role": "user", "content": "2+2?"}, {"role": "assistant", "content": "4"}]}',
    ]
    return "\n".join(lines).encode()


def test_non_admin_cannot_upload_dataset(client):
    # Fine-tuning is admin-only — see training.py's get_current_admin gate.
    token = _register_and_login(client, "not-an-admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("train.jsonl", io.BytesIO(_valid_jsonl()), "application/octet-stream")},
    )
    assert resp.status_code == 403


def test_valid_dataset_is_validated(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "trainer@example.com")
    try:
        token = _register_and_login(client, "trainer@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/datasets",
            headers=headers,
            files={"file": ("train.jsonl", io.BytesIO(_valid_jsonl()), "application/octet-stream")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "VALIDATED"
        assert body["num_examples"] == 2
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_invalid_dataset_is_marked_invalid(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "bad-trainer@example.com")
    try:
        token = _register_and_login(client, "bad-trainer@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        bad_content = b'{"messages": [{"role": "user", "content": "Hi"}]}\n'  # missing assistant turn
        resp = client.post(
            "/api/v1/datasets",
            headers=headers,
            files={"file": ("train.jsonl", io.BytesIO(bad_content), "application/octet-stream")},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "INVALID"
        assert resp.json()["error_message"] is not None
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_rejects_non_jsonl_extension(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "wrong-ext@example.com")
    try:
        token = _register_and_login(client, "wrong-ext@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post(
            "/api/v1/datasets",
            headers=headers,
            files={"file": ("train.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        )
        assert resp.status_code == 415
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_training_job_requires_validated_dataset(client, monkeypatch):
    # Prevent actually spawning the (unavailable, torch-less) training subprocess in tests.
    monkeypatch.setattr("app.api.v1.endpoints.training.launch_training_job", lambda *a, **k: None)
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "job-user@example.com")
    try:
        token = _register_and_login(client, "job-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        bad_content = b'{"messages": [{"role": "user", "content": "Hi"}]}\n'
        dataset = client.post(
            "/api/v1/datasets",
            headers=headers,
            files={"file": ("bad.jsonl", io.BytesIO(bad_content), "application/octet-stream")},
        ).json()

        resp = client.post(
            "/api/v1/training-jobs",
            json={"dataset_id": dataset["id"], "base_model": "meta-llama/Llama-3.2-1B"},
            headers=headers,
        )
        assert resp.status_code == 400
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_training_job_created_for_validated_dataset(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.training.launch_training_job", lambda *a, **k: None)
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "job-user2@example.com")
    try:
        token = _register_and_login(client, "job-user2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        dataset = client.post(
            "/api/v1/datasets",
            headers=headers,
            files={"file": ("train.jsonl", io.BytesIO(_valid_jsonl()), "application/octet-stream")},
        ).json()

        resp = client.post(
            "/api/v1/training-jobs",
            json={"dataset_id": dataset["id"], "base_model": "meta-llama/Llama-3.2-1B"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "PENDING"
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_launch_training_job_spawns_a_real_separate_process(tmp_path):
    # No training/.venv provisioned here, so this falls back to the backend's own interpreter
    # running training/scripts/train_lora.py, which has SQLAlchemy but not torch/transformers —
    # it should run as a genuine child process (proving the subprocess/DB-status plumbing is
    # real) and fail fast with a clear "install training deps" message, never fake success.
    proc = launch_training_job("smoke-test-job", "dataset.jsonl", "meta-llama/Llama-3.2-1B", str(tmp_path))
    assert proc.pid is not None
    proc.wait(timeout=30)
