from app.core.config import get_settings
from app.db.models.code_project import CodeProject
from app.db.models.model_registry import RegisteredModel
from app.db.models.user import User
from app.main import app
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider
from app.services.model_registry_service import discover_local_models, guess_capability
from app.services.model_router import FrontierModelRouter

settings = get_settings()


class _FakeEmbeddingProvider(EmbeddingProvider):
    """Trivial fixed-vector embedder — these tests exercise routing, not retrieval quality."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_guess_capability_heuristics():
    assert guess_capability("qwen2.5-coder:1.5b") == "CODE"
    assert guess_capability("moondream") == "VISION"
    assert guess_capability("all-minilm") == "EMBEDDING"
    assert guess_capability("llama3.2:1b") == "TEXT"


async def test_discover_registers_new_models_only(db_session):
    mock = MockProvider(models=["llama3.2:1b", "qwen2.5-coder:1.5b"])

    first = await discover_local_models(db_session, mock)
    assert {m.base_model for m in first} == {"llama3.2:1b", "qwen2.5-coder:1.5b"}
    assert all(m.status == "EXPERIMENTAL" and m.provider == "LOCAL" for m in first)
    assert {m.capability for m in first} == {"TEXT", "CODE"}

    # Idempotent: nothing new to discover on a second pass.
    second = await discover_local_models(db_session, mock)
    assert second == []
    assert db_session.query(RegisteredModel).count() == 2


async def test_discover_skips_already_registered_base_models(db_session):
    db_session.add(
        RegisteredModel(
            name="local-llama3.2:1b",
            base_model="llama3.2:1b",
            capability="TEXT",
            provider="LOCAL",
            location="ollama://llama3.2:1b",
            status="PRODUCTION",
        )
    )
    db_session.commit()

    mock = MockProvider(models=["llama3.2:1b"])
    found = await discover_local_models(db_session, mock)
    assert found == []
    assert db_session.query(RegisteredModel).count() == 1


def test_router_selects_highest_eval_score_production_model(db_session):
    low = RegisteredModel(
        name="low", base_model="model-a", capability="TEXT", provider="LOCAL",
        location="ollama://model-a", status="PRODUCTION", eval_score=0.2,
    )
    high = RegisteredModel(
        name="high", base_model="model-b", capability="TEXT", provider="LOCAL",
        location="ollama://model-b", status="PRODUCTION", eval_score=0.9,
    )
    experimental = RegisteredModel(
        name="exp", base_model="model-c", capability="TEXT", provider="LOCAL",
        location="ollama://model-c", status="EXPERIMENTAL", eval_score=0.99,
    )
    db_session.add_all([low, high, experimental])
    db_session.commit()

    chosen = FrontierModelRouter().select(db_session, "TEXT")
    assert chosen.base_model == "model-b"  # highest eval_score among PRODUCTION rows


def test_router_bootstraps_settings_default_when_nothing_registered(db_session):
    assert db_session.query(RegisteredModel).count() == 0

    chosen = FrontierModelRouter().select(db_session, "CODE")
    assert chosen.base_model == settings.ollama_code_model
    assert chosen.status == "PRODUCTION"
    assert chosen.provider == "LOCAL"

    # Second call finds the now-registered row directly rather than bootstrapping again.
    again = FrontierModelRouter().select(db_session, "CODE")
    assert again.id == chosen.id
    assert db_session.query(RegisteredModel).count() == 1


def test_router_ignores_non_local_and_non_production_rows(db_session):
    db_session.add_all(
        [
            RegisteredModel(
                name="cloud", base_model="gpt-x", capability="TEXT", provider="OPENAI",
                location="openai://gpt-x", status="PRODUCTION", eval_score=1.0,
            ),
            RegisteredModel(
                name="canary", base_model="model-canary", capability="TEXT", provider="LOCAL",
                location="ollama://model-canary", status="CANARY", eval_score=1.0,
            ),
        ]
    )
    db_session.commit()

    # Neither candidate qualifies, so the router falls back to bootstrapping the default.
    chosen = FrontierModelRouter().select(db_session, "TEXT")
    assert chosen.base_model == settings.ollama_model


def test_code_project_conversation_routes_to_code_capability(client, db_session):
    mock = MockProvider(reply="ok")
    app.dependency_overrides[get_llm_client] = lambda: mock
    app.dependency_overrides[get_embedding_provider] = lambda: _FakeEmbeddingProvider()
    try:
        token = _register_and_login(client, "coder-route@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        user = db_session.query(User).filter(User.email == "coder-route@example.com").one()

        project = CodeProject(user_id=user.id, name="proj", storage_dir="/tmp/proj", status="READY")
        db_session.add(project)
        db_session.commit()

        conv = client.post("/api/v1/conversations", json={"code_project_id": str(project.id)}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            "".join(resp.iter_text())

        assert mock.last_model == settings.ollama_code_model
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
        app.dependency_overrides.pop(get_embedding_provider, None)


def test_explicit_conversation_model_overrides_router(client):
    mock = MockProvider(reply="ok")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "pin-route@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={"model": "custom-pinned-model"}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            "".join(resp.iter_text())

        assert mock.last_model == "custom-pinned-model"
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_discover_endpoint_requires_admin(client):
    token = _register_and_login(client, "not-admin@example.com")
    resp = client.post("/api/v1/admin/models/discover", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_discover_endpoint_registers_and_returns_new_models(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "registry-admin@example.com")
    try:
        monkeypatch.setattr(
            "app.api.v1.endpoints.admin.get_llm_client",
            lambda: MockProvider(models=["llama3.2:1b", "moondream"]),
        )
        token = _register_and_login(client, "registry-admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/admin/models/discover", headers=headers)
        assert resp.status_code == 200
        names = {m["base_model"] for m in resp.json()}
        assert names == {"llama3.2:1b", "moondream"}
        capabilities = {m["base_model"]: m["capability"] for m in resp.json()}
        assert capabilities["moondream"] == "VISION"

        again = client.post("/api/v1/admin/models/discover", headers=headers)
        assert again.json() == []
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()
