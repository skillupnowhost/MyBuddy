from app.core.config import get_settings


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_non_admin_gets_403(client):
    token = _register_and_login(client, "regular-user@example.com")
    resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_email_is_auto_promoted(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    try:
        token = _register_and_login(client, "boss@example.com")
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["role"] == "ADMIN"

        stats = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert stats.status_code == 200
        assert stats.json()["total_users"] == 1
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_admin_can_list_and_promote_users(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "root@example.com")
    try:
        admin_token = _register_and_login(client, "root@example.com")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        _register_and_login(client, "employee@example.com")

        users = client.get("/api/v1/admin/users", headers=admin_headers)
        assert users.status_code == 200
        assert len(users.json()) == 2

        employee = next(u for u in users.json() if u["email"] == "employee@example.com")
        promoted = client.patch(
            f"/api/v1/admin/users/{employee['id']}/role", json={"role": "ADMIN"}, headers=admin_headers
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "ADMIN"
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_admin_cannot_demote_self(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "solo-admin@example.com")
    try:
        token = _register_and_login(client, "solo-admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/v1/auth/me", headers=headers).json()

        resp = client.patch(f"/api/v1/admin/users/{me['id']}/role", json={"role": "USER"}, headers=headers)
        assert resp.status_code == 400
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()
