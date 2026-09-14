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
