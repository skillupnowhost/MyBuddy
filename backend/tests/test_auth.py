def test_register_and_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "supersecret123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "hashed_password" not in body

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "supersecret123"},
    )
    assert resp.status_code == 200
    tokens = resp.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]


def test_duplicate_registration_rejected(client):
    payload = {"email": "bob@example.com", "password": "supersecret123"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 400


def test_login_with_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": "supersecret123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_conversation_requires_auth(client):
    resp = client.get("/api/v1/conversations")
    assert resp.status_code == 401
