from app.core.config import get_settings
from app.db.models.model_benchmark_result import ModelBenchmarkResult
from app.db.models.model_registry import RegisteredModel
from app.services.benchmark_service import BenchmarkPrompt, run_benchmark, score_response
from app.services.mock_provider import MockProvider
from app.services.model_router import FrontierModelRouter

settings = get_settings()


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_score_response_word_overlap():
    prompt = BenchmarkPrompt("p1", "What is 12 plus 30?", reference_answer="42")
    assert score_response(prompt, "42") == 1.0
    assert score_response(prompt, "The answer is 42.") > 0.0
    assert score_response(prompt, "banana") == 0.0


def test_score_response_keyword_presence():
    prompt = BenchmarkPrompt("p2", "List colors", required_keywords=["red", "blue", "yellow"])
    assert score_response(prompt, "red, blue, and yellow") == 1.0
    assert score_response(prompt, "red only") == 1 / 3
    assert score_response(prompt, "green") == 0.0


def test_score_response_with_no_reference_or_keywords_is_zero():
    prompt = BenchmarkPrompt("p3", "Say anything")
    assert score_response(prompt, "hello") == 0.0


async def test_run_benchmark_writes_results_and_eval_score(db_session):
    model = RegisteredModel(
        name="local-llama3.2:1b", base_model="llama3.2:1b", capability="TEXT", provider="LOCAL",
        location="ollama://llama3.2:1b", status="PRODUCTION",
    )
    db_session.add(model)
    db_session.commit()

    # 4 TEXT prompts defined -> 4 canned replies, one exact match each so scoring is deterministic.
    mock = MockProvider(replies=["42", "Paris", "ready", "red\nblue\nyellow"])
    results = await run_benchmark(db_session, mock, model)

    assert len(results) == 4
    assert all(r.model_id == model.id for r in results)
    assert db_session.query(ModelBenchmarkResult).count() == 4
    db_session.refresh(model)
    assert model.eval_score == sum(r.score for r in results) / len(results)
    assert model.eval_score > 0.9  # near-perfect canned answers


async def test_run_benchmark_returns_empty_for_capability_without_suite(db_session):
    model = RegisteredModel(
        name="local-moondream", base_model="moondream", capability="VISION", provider="LOCAL",
        location="ollama://moondream", status="PRODUCTION", eval_score=None,
    )
    db_session.add(model)
    db_session.commit()

    mock = MockProvider(reply="a cat")
    results = await run_benchmark(db_session, mock, model)
    assert results == []
    db_session.refresh(model)
    assert model.eval_score is None


def test_benchmark_endpoint_requires_admin(client):
    token = _register_and_login(client, "not-admin-bench@example.com")
    resp = client.post(
        "/api/v1/admin/models/00000000-0000-0000-0000-000000000000/benchmark",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_benchmark_endpoint_runs_and_updates_score(client, monkeypatch, db_session):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "bench-admin@example.com")
    try:
        monkeypatch.setattr(
            "app.api.v1.endpoints.admin.get_llm_client",
            lambda: MockProvider(replies=["42", "Paris", "ready", "red\nblue\nyellow"]),
        )
        token = _register_and_login(client, "bench-admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        model = RegisteredModel(
            name="local-llama3.2:1b", base_model="llama3.2:1b", capability="TEXT", provider="LOCAL",
            location="ollama://llama3.2:1b", status="EXPERIMENTAL",
        )
        db_session.add(model)
        db_session.commit()

        resp = client.post(f"/api/v1/admin/models/{model.id}/benchmark", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 4
        assert body["eval_score"] > 0.9

        listed = client.get(f"/api/v1/admin/models/{model.id}/benchmark", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 4
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


def test_router_prefers_the_model_with_higher_benchmark_score(db_session):
    weak = RegisteredModel(
        name="weak", base_model="model-weak", capability="TEXT", provider="LOCAL",
        location="ollama://model-weak", status="PRODUCTION", eval_score=0.3,
    )
    strong = RegisteredModel(
        name="strong", base_model="model-strong", capability="TEXT", provider="LOCAL",
        location="ollama://model-strong", status="PRODUCTION", eval_score=0.95,
    )
    db_session.add_all([weak, strong])
    db_session.commit()

    chosen = FrontierModelRouter().select(db_session, "TEXT")
    assert chosen.base_model == "model-strong"
