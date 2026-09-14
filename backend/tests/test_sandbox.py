import pytest

from app.core.config import get_settings
from app.services.sandbox_provider import UnsupportedLanguage
from app.services.subprocess_sandbox import SubprocessSandboxProvider

settings = get_settings()


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_submit_execution_requires_admin(client):
    token = _register_and_login(client, "not-an-admin@example.com")
    resp = client.post(
        "/api/v1/code/execute",
        json={"language": "python", "source": "print('hi')"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_execution_captures_real_stdout(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "sandbox-admin@example.com")
    try:
        token = _register_and_login(client, "sandbox-admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/api/v1/code/execute",
            json={"language": "python", "source": "print('hello from sandbox')"},
            headers=headers,
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        # TestClient runs BackgroundTasks synchronously as part of the request, so the job
        # has already finished by the time this GET runs.
        detail = client.get(f"/api/v1/code/execute/{job_id}", headers=headers)
        body = detail.json()
        assert body["status"] == "COMPLETED"
        assert body["stdout"].strip() == "hello from sandbox"
        assert body["exit_code"] == 0
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_execution_isolated_per_user(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "admin-owner@example.com,admin-intruder@example.com")
    try:
        token_a = _register_and_login(client, "admin-owner@example.com")
        token_b = _register_and_login(client, "admin-intruder@example.com")

        resp = client.post(
            "/api/v1/code/execute",
            json={"language": "python", "source": "print('a')"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        job_id = resp.json()["id"]

        forbidden = client.get(f"/api/v1/code/execute/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert forbidden.status_code == 404
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_unsupported_language_is_rejected_before_running(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "lang-admin@example.com")
    try:
        token = _register_and_login(client, "lang-admin@example.com")
        resp = client.post(
            "/api/v1/code/execute",
            json={"language": "ruby", "source": "puts 'hi'"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


# --- Direct SubprocessSandboxProvider tests (real subprocesses, nothing mocked) ---


@pytest.mark.asyncio
async def test_sandbox_provider_real_timeout_kills_process(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_timeout_seconds", 1)
    provider = SubprocessSandboxProvider()
    result = await provider.run("python", "import time\ntime.sleep(30)\n")
    assert result.timed_out is True


@pytest.mark.asyncio
async def test_sandbox_provider_truncates_large_output(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_max_output_bytes", 100)
    provider = SubprocessSandboxProvider()
    result = await provider.run("python", "print('x' * 10000)")
    assert result.stdout_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 100


@pytest.mark.asyncio
async def test_sandbox_provider_env_excludes_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://leak-me-if-you-can")
    provider = SubprocessSandboxProvider()
    result = await provider.run(
        "python",
        "import os, sys; sys.stdout.write('LEAK' if 'DATABASE_URL' in os.environ else 'CLEAN')",
    )
    assert result.stdout == "CLEAN"


@pytest.mark.asyncio
async def test_sandbox_provider_rejects_unsupported_language():
    provider = SubprocessSandboxProvider()
    with pytest.raises(UnsupportedLanguage):
        await provider.run("ruby", "puts 'hi'")
