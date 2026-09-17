import json

from app.main import app
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider


def _reconstruct_sse_content(raw_body: str) -> str:
    content = ""
    for line in raw_body.split("\n\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = json.loads(line[len("data:") :].strip())
        content += payload.get("delta", "")
    return content


def _register_and_login(client, email="dave@example.com", password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_send_message_streams_and_persists(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="Hello there!")
    try:
        token = _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        conv_resp = client.post("/api/v1/conversations", json={}, headers=headers)
        assert conv_resp.status_code == 201
        conversation_id = conv_resp.json()["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "hi"},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
        assert _reconstruct_sse_content(body) == "Hello there!"

        history = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers)
        assert history.status_code == 200
        messages = history.json()
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[1]["content"] == "Hello there!"
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_delete_message_onward_removes_target_and_later_messages(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="reply")
    try:
        token = _register_and_login(client, email="frank@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conversation_id = client.post("/api/v1/conversations", json={}, headers=headers).json()["id"]

        # Two full turns, so there's a "later" turn to prove gets deleted too.
        for content in ["first", "second"]:
            with client.stream(
                "POST",
                f"/api/v1/conversations/{conversation_id}/messages",
                json={"content": content},
                headers=headers,
            ) as resp:
                assert resp.status_code == 200
                "".join(resp.iter_text())

        before = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).json()
        assert [m["content"] for m in before] == ["first", "reply", "second", "reply"]
        first_message_id = before[0]["id"]

        del_resp = client.delete(
            f"/api/v1/conversations/{conversation_id}/messages/{first_message_id}/onward", headers=headers
        )
        assert del_resp.status_code == 204

        after = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).json()
        assert after == []
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_get_message_detail_returns_one_message(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="reply")
    try:
        token = _register_and_login(client, email="ivy@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conversation_id = client.post("/api/v1/conversations", json={}, headers=headers).json()["id"]
        with client.stream(
            "POST",
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "hi"},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            "".join(resp.iter_text())

        messages = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).json()
        assistant_id = next(m["id"] for m in messages if m["role"] == "assistant")

        detail = client.get(
            f"/api/v1/conversations/{conversation_id}/messages/{assistant_id}",
            headers=headers,
        )
        assert detail.status_code == 200
        assert detail.json()["id"] == assistant_id
        assert detail.json()["role"] == "assistant"
        assert detail.json()["content"] == "reply"
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_message_feedback_set_and_clear(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(reply="reply")
    try:
        token = _register_and_login(client, email="ivy@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conversation_id = client.post("/api/v1/conversations", json={}, headers=headers).json()["id"]
        with client.stream(
            "POST",
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "hi"},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200
            "".join(resp.iter_text())

        messages = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).json()
        assistant_id = next(m["id"] for m in messages if m["role"] == "assistant")

        up = client.patch(
            f"/api/v1/conversations/{conversation_id}/messages/{assistant_id}",
            json={"feedback": "up"},
            headers=headers,
        )
        assert up.status_code == 200
        assert up.json()["feedback"] == "up"

        cleared = client.patch(
            f"/api/v1/conversations/{conversation_id}/messages/{assistant_id}",
            json={"feedback": None},
            headers=headers,
        )
        assert cleared.status_code == 200
        assert cleared.json()["feedback"] is None
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_delete_message_onward_requires_ownership(client):
    token_a = _register_and_login(client, email="grace@example.com")
    token_b = _register_and_login(client, email="heidi@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    conversation_id = client.post("/api/v1/conversations", json={}, headers=headers_a).json()["id"]

    resp = client.delete(
        f"/api/v1/conversations/{conversation_id}/messages/{conversation_id}/onward", headers=headers_b
    )
    assert resp.status_code == 404


def test_message_create_uses_a_fresh_image_list_per_instance():
    from app.schemas.message import MessageCreate

    first = MessageCreate(content="hello")
    second = MessageCreate(content="there")

    first.image_ids.append("not-a-uuid")

    assert first.image_ids == ["not-a-uuid"]
    assert second.image_ids == []


def test_list_models(client):
    app.dependency_overrides[get_llm_client] = lambda: MockProvider(models=["llama3.2:1b"])
    try:
        token = _register_and_login(client, email="erin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/api/v1/models", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["models"] == ["llama3.2:1b"]
        assert "default_model" in body
        assert "code_model" in body
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
