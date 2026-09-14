import io
import json

from app.main import app
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """Every text gets the same trivial vector — plumbing test, not a semantic-quality test.
    The real PostgresVectorStoreProvider is used as-is; it only needs a DB session and numpy."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _override_embeddings():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()


def test_upload_document_gets_ingested_and_ready(client, db_session):
    _override_embeddings()
    try:
        token = _register_and_login(client, "docs-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        file_content = b"MyBuddy is a self-hosted AI assistant. It runs entirely on local infrastructure."
        resp = client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": ("notes.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert resp.status_code == 201
        doc = resp.json()
        assert doc["filename"] == "notes.txt"

        detail = client.get(f"/api/v1/documents/{doc['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["status"] == "READY"
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_rejects_unsupported_file_type(client):
    token = _register_and_login(client, "bad-upload@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
    )
    assert resp.status_code == 415


def test_document_access_is_isolated_per_user(client, db_session):
    _override_embeddings()
    try:
        token_a = _register_and_login(client, "owner@example.com")
        token_b = _register_and_login(client, "intruder@example.com")

        resp = client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("private.txt", io.BytesIO(b"secret content"), "text/plain")},
        )
        doc_id = resp.json()["id"]

        forbidden = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert forbidden.status_code == 404
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_rag_enabled_conversation_includes_sources(client, db_session):
    _override_embeddings()
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="Here is the answer.")
    try:
        token = _register_and_login(client, "rag-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": ("kb.txt", io.BytesIO(b"The secret code is MYBUDDY42."), "text/plain")},
        )

        conv = client.post("/api/v1/conversations", json={"rag_enabled": True}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "What is the secret code?"},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

        events = [json.loads(line[len("data:") :].strip()) for line in body.split("\n\n") if line.startswith("data:")]
        sources_events = [e for e in events if "sources" in e]
        assert len(sources_events) == 1
        assert sources_events[0]["sources"][0]["filename"] == "kb.txt"
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_client, None)


def test_rag_isolated_per_user(client, db_session):
    """A RAG-enabled conversation must never surface another user's document content."""
    _override_embeddings()
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="Answer.")
    try:
        token_a = _register_and_login(client, "rag-owner@example.com")
        token_b = _register_and_login(client, "rag-intruder@example.com")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        client.post(
            "/api/v1/documents",
            headers=headers_a,
            files={"file": ("owner-only.txt", io.BytesIO(b"Owner's private data."), "text/plain")},
        )

        conv = client.post("/api/v1/conversations", json={"rag_enabled": True}, headers=headers_b)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Tell me anything."},
            headers=headers_b,
        ) as resp:
            body = "".join(resp.iter_text())

        events = [json.loads(line[len("data:") :].strip()) for line in body.split("\n\n") if line.startswith("data:")]
        sources_events = [e for e in events if "sources" in e]
        assert sources_events == []
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_client, None)
