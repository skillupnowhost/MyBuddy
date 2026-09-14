import io
import os
import zipfile

from app.core.config import get_settings
from app.main import app
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider

settings = get_settings()


class FakeEmbeddingProvider(EmbeddingProvider):
    """Every text gets the same trivial vector — plumbing test, not a semantic-quality test."""

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


def test_zip_upload_extracts_and_ingests_project(client, db_session):
    _override_embeddings()
    try:
        token = _register_and_login(client, "coder@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        zip_bytes = _make_zip(
            {
                "src/main.py": "def main():\n    print('hello')\n",
                "src/utils.py": "def add(a, b):\n    return a + b\n",
            }
        )
        resp = client.post(
            "/api/v1/code/projects",
            headers=headers,
            files={"file": ("myproj.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
        assert resp.status_code == 201
        project = resp.json()
        assert project["file_count"] == 2

        detail = client.get(f"/api/v1/code/projects/{project['id']}", headers=headers)
        assert detail.json()["status"] == "READY"

        tree = client.get(f"/api/v1/code/projects/{project['id']}/tree", headers=headers)
        paths = sorted(f["relative_path"] for f in tree.json())
        assert paths == ["src/main.py", "src/utils.py"]

        file_id = next(f["id"] for f in tree.json() if f["relative_path"] == "src/main.py")
        content_resp = client.get(f"/api/v1/code/projects/{project['id']}/files/{file_id}", headers=headers)
        assert "def main" in content_resp.json()["content"]
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_zip_path_traversal_entries_are_rejected(client, db_session):
    _override_embeddings()
    try:
        token = _register_and_login(client, "traversal@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(zipfile.ZipInfo("../../evil.py"), "print('pwned')\n")
            zf.writestr("safe.py", "print('ok')\n")

        resp = client.post(
            "/api/v1/code/projects",
            headers=headers,
            files={"file": ("evil.zip", io.BytesIO(buf.getvalue()), "application/zip")},
        )
        assert resp.status_code == 201
        project = resp.json()

        tree = client.get(f"/api/v1/code/projects/{project['id']}/tree", headers=headers)
        paths = [f["relative_path"] for f in tree.json()]
        assert paths == ["safe.py"]

        # No file should have been written outside storage_dir at all.
        escaped_path = os.path.normpath(os.path.join(settings.storage_dir, "code_projects", "..", "..", "evil.py"))
        assert not os.path.exists(escaped_path)
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_zip_entry_count_over_cap_is_rejected(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "code_max_files_per_project", 3)
    token = _register_and_login(client, "manyfiles@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    zip_bytes = _make_zip({f"file{i}.py": "pass\n" for i in range(10)})
    resp = client.post(
        "/api/v1/code/projects",
        headers=headers,
        files={"file": ("many.zip", io.BytesIO(zip_bytes), "application/zip")},
    )
    assert resp.status_code == 400


def test_zip_bomb_compression_ratio_entry_is_skipped(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "code_max_compression_ratio", 5)
    _override_embeddings()
    try:
        token = _register_and_login(client, "zipbomb@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # ZipFile defaults to ZIP_STORED (no compression) unless told otherwise, which would
        # make compress_size == file_size and hide the ratio check entirely — force
        # ZIP_DEFLATED so this test actually exercises compression, like a real zip bomb would.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.txt", "0" * 200_000)  # highly compressible -> ratio far exceeds the monkeypatched cap
            zf.writestr("normal.py", "print('hello world, this line does not compress trivially')\n")
        resp = client.post(
            "/api/v1/code/projects",
            headers=headers,
            files={"file": ("bomb.zip", io.BytesIO(buf.getvalue()), "application/zip")},
        )
        assert resp.status_code == 201
        project = resp.json()
        tree = client.get(f"/api/v1/code/projects/{project['id']}/tree", headers=headers)
        paths = [f["relative_path"] for f in tree.json()]
        assert "bomb.txt" not in paths
        assert "normal.py" in paths
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_code_project_access_is_isolated_per_user(client, db_session):
    _override_embeddings()
    try:
        token_a = _register_and_login(client, "code-owner@example.com")
        token_b = _register_and_login(client, "code-intruder@example.com")

        zip_bytes = _make_zip({"secret.py": "SECRET = 42\n"})
        resp = client.post(
            "/api/v1/code/projects",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("private.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
        project_id = resp.json()["id"]

        forbidden = client.get(
            f"/api/v1/code/projects/{project_id}", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert forbidden.status_code == 404
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_conversation_cannot_be_scoped_to_another_users_code_project(client, db_session):
    _override_embeddings()
    try:
        token_a = _register_and_login(client, "proj-owner@example.com")
        token_b = _register_and_login(client, "proj-intruder@example.com")

        zip_bytes = _make_zip({"a.py": "A = 1\n"})
        resp = client.post(
            "/api/v1/code/projects",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("a.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
        project_id = resp.json()["id"]

        conv = client.post(
            "/api/v1/conversations",
            json={"code_project_id": project_id},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert conv.status_code == 404
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
