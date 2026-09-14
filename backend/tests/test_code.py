import io
import zipfile

from app.core.config import get_settings
from app.main import app
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider

settings = get_settings()


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _override_embeddings():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_rejects_non_zip_upload(client):
    token = _register_and_login(client, "not-a-zip@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/code/projects",
        headers=headers,
        files={"file": ("notes.txt", io.BytesIO(b"just text"), "text/plain")},
    )
    assert resp.status_code == 415


def test_rejects_empty_zip_upload(client):
    token = _register_and_login(client, "empty-zip@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/code/projects",
        headers=headers,
        files={"file": ("empty.zip", io.BytesIO(b""), "application/zip")},
    )
    assert resp.status_code == 400


def test_rejects_oversized_zip_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "code_max_zip_size_bytes", 100)
    token = _register_and_login(client, "big-zip@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    zip_bytes = _make_zip({f"file{i}.py": "x = 1\n" * 50 for i in range(5)})
    assert len(zip_bytes) > 100
    resp = client.post(
        "/api/v1/code/projects",
        headers=headers,
        files={"file": ("big.zip", io.BytesIO(zip_bytes), "application/zip")},
    )
    assert resp.status_code == 413


def test_rejects_zip_with_no_supported_source_files(client):
    token = _register_and_login(client, "no-source@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    zip_bytes = _make_zip({"image.png": "not really a png but wrong extension anyway"})
    resp = client.post(
        "/api/v1/code/projects",
        headers=headers,
        files={"file": ("noext.zip", io.BytesIO(zip_bytes), "application/zip")},
    )
    assert resp.status_code == 400


def test_delete_project_removes_it(client, db_session):
    _override_embeddings()
    try:
        token = _register_and_login(client, "deleter@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        zip_bytes = _make_zip({"a.py": "A = 1\n"})
        resp = client.post(
            "/api/v1/code/projects",
            headers=headers,
            files={"file": ("a.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
        project_id = resp.json()["id"]
        assert client.get(f"/api/v1/code/projects/{project_id}", headers=headers).status_code == 200

        deleted = client.delete(f"/api/v1/code/projects/{project_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/code/projects/{project_id}", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
