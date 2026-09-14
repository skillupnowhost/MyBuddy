import pytest

from app.services.memory_service import extract_and_save_memories, get_memory_context
from app.services.mock_provider import MockProvider


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_manual_memory_crud(client):
    token = _register_and_login(client, "memory-user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/memories", json={"content": "Prefers concise answers."}, headers=headers)
    assert resp.status_code == 201
    memory_id = resp.json()["id"]
    assert resp.json()["source"] == "manual"

    listed = client.get("/api/v1/memories", headers=headers)
    assert len(listed.json()) == 1

    deleted = client.delete(f"/api/v1/memories/{memory_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/memories", headers=headers).json() == []


def test_memory_isolated_per_user(client):
    token_a = _register_and_login(client, "mem-owner@example.com")
    token_b = _register_and_login(client, "mem-intruder@example.com")

    resp = client.post(
        "/api/v1/memories", json={"content": "secret"}, headers={"Authorization": f"Bearer {token_a}"}
    )
    memory_id = resp.json()["id"]

    forbidden = client.delete(f"/api/v1/memories/{memory_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_extract_and_save_memories_parses_and_dedupes(db_session, db_engine):
    from sqlalchemy.orm import sessionmaker

    # A real session factory, matching production: each call opens an independent session
    # (extract_and_save_memories closes it when done) rather than reusing this test's own.
    session_factory = sessionmaker(bind=db_engine)

    llm = MockProvider(reply='["Lives in Berlin.", "Prefers Python over JavaScript."]')

    from app.core.security import hash_password
    from app.db.models.user import User

    user = User(email="extract@example.com", hashed_password=hash_password("supersecret123"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    await extract_and_save_memories(session_factory, llm, "mock-model", user.id, "I live in Berlin", "Noted!")

    context = get_memory_context(db_session, user.id)
    assert context is not None
    assert "Berlin" in context

    # Running again with the same facts must not duplicate them.
    await extract_and_save_memories(session_factory, llm, "mock-model", user.id, "I live in Berlin", "Noted!")
    from app.db.models.memory import Memory

    assert db_session.query(Memory).filter(Memory.user_id == user.id).count() == 2
