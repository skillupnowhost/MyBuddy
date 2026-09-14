from app.core.config import get_settings
from app.db.models.conversation import Conversation
from app.db.models.max_mode_candidate import MaxModeCandidate
from app.db.models.message import Message
from app.db.models.model_registry import RegisteredModel
from app.db.models.user import User
from app.main import app
from app.services.arena_service import run_arena_comparison
from app.services.llm_client import get_llm_client
from app.services.max_mode_service import generate_max_mode_reply, get_max_mode_candidates
from app.services.mock_provider import MockProvider

settings = get_settings()


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _two_text_models(db_session, statuses=("PRODUCTION", "PRODUCTION")):
    a = RegisteredModel(
        name="a", base_model="model-a", capability="TEXT", provider="LOCAL",
        location="ollama://model-a", status=statuses[0], eval_score=0.9,
    )
    b = RegisteredModel(
        name="b", base_model="model-b", capability="TEXT", provider="LOCAL",
        location="ollama://model-b", status=statuses[1], eval_score=0.5,
    )
    db_session.add_all([a, b])
    db_session.commit()
    return a, b


# --- arena_service -----------------------------------------------------------------------


async def test_run_arena_comparison_empty_when_no_candidates(db_session):
    results = await run_arena_comparison(db_session, MockProvider(), "TEXT", "hi")
    assert results == []


async def test_run_arena_comparison_runs_all_candidates_and_shares_comparison_id(db_session):
    _two_text_models(db_session, statuses=("PRODUCTION", "EXPERIMENTAL"))  # arena includes EXPERIMENTAL
    mock = MockProvider(replies=["reply A", "reply B"])

    results = await run_arena_comparison(db_session, mock, "TEXT", "what is 2+2?")

    assert len(results) == 2
    assert len({r.comparison_id for r in results}) == 1
    assert {r.response for r in results} == {"reply A", "reply B"}
    assert all(r.score is None for r in results)  # no reference_answer given


async def test_run_arena_comparison_scores_against_reference(db_session):
    _two_text_models(db_session)
    mock = MockProvider(replies=["42", "banana"])

    results = await run_arena_comparison(db_session, mock, "TEXT", "2+2?", reference_answer="42")

    by_response = {r.response: r.score for r in results}
    assert by_response["42"] == 1.0
    assert by_response["banana"] == 0.0


def test_arena_compare_endpoint_requires_admin(client):
    token = _register_and_login(client, "not-admin-arena@example.com")
    resp = client.post(
        "/api/v1/admin/arena/compare",
        json={"capability": "TEXT", "prompt": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_arena_compare_endpoint_runs_and_history_lists_it(client, monkeypatch, db_session):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "arena-admin@example.com")
    try:
        monkeypatch.setattr(
            "app.api.v1.endpoints.admin.get_llm_client",
            lambda: MockProvider(replies=["reply A", "reply B"]),
        )
        token = _register_and_login(client, "arena-admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        _two_text_models(db_session)

        resp = client.post(
            "/api/v1/admin/arena/compare", json={"capability": "TEXT", "prompt": "hi"}, headers=headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        history = client.get("/api/v1/admin/arena/history", headers=headers)
        assert history.status_code == 200
        assert len(history.json()) == 2

        scoped = client.get("/api/v1/admin/arena/history?capability=CODE", headers=headers)
        assert scoped.json() == []
    finally:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        get_settings.cache_clear()


# --- max_mode_service ---------------------------------------------------------------------


def test_get_max_mode_candidates_excludes_experimental(db_session):
    _two_text_models(db_session, statuses=("PRODUCTION", "EXPERIMENTAL"))
    candidates = get_max_mode_candidates(db_session, "TEXT")
    assert [c.base_model for c in candidates] == ["model-a"]


def test_get_max_mode_candidates_orders_by_eval_score(db_session):
    a, b = _two_text_models(db_session)  # a: 0.9, b: 0.5
    candidates = get_max_mode_candidates(db_session, "TEXT")
    assert [c.id for c in candidates] == [a.id, b.id]


async def test_generate_max_mode_reply_synthesizes_via_top_candidate_as_judge(db_session):
    a, b = _two_text_models(db_session)
    mock = MockProvider(replies=["candidate A answer", "candidate B answer", "final synthesized answer"])
    history = [{"role": "user", "content": "what should I do?"}]

    synthesized, results = await generate_max_mode_reply(mock, history, [a, b])

    assert synthesized == "final synthesized answer"
    assert len(results) == 3  # 2 raw candidates + 1 judge synthesis
    judge_rows = [r for r in results if r.is_judge]
    assert len(judge_rows) == 1
    assert judge_rows[0].model.id == a.id  # highest eval_score is the judge
    assert judge_rows[0].response == "final synthesized answer"


# --- chat_service integration ---------------------------------------------------------------


def test_max_mode_conversation_fans_out_and_persists_candidates(client, db_session):
    mock = MockProvider(replies=["candidate A answer", "candidate B answer", "final synthesized answer"])
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "max-mode-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        _two_text_models(db_session)

        conv = client.post("/api/v1/conversations", json={"max_mode_enabled": True}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "max_mode_models" in body

        assistant_message = (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .one()
        )
        assert assistant_message.content == "final synthesized answer"

        candidates = (
            db_session.query(MaxModeCandidate).filter(MaxModeCandidate.message_id == assistant_message.id).all()
        )
        assert len(candidates) == 3
        assert sum(1 for c in candidates if c.is_judge) == 1

        listed = client.get(
            f"/api/v1/conversations/{conv_id}/messages/{assistant_message.id}/max-candidates", headers=headers
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 3
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_max_mode_falls_back_to_single_model_with_fewer_than_two_candidates(client, db_session):
    mock = MockProvider(reply="normal single-model reply")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "max-mode-fallback@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        # Only one PRODUCTION TEXT model registered -> MAX mode is a documented no-op.
        db_session.add(
            RegisteredModel(
                name="solo", base_model="model-solo", capability="TEXT", provider="LOCAL",
                location="ollama://model-solo", status="PRODUCTION",
            )
        )
        db_session.commit()

        conv = client.post("/api/v1/conversations", json={"max_mode_enabled": True}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "max_mode_models" not in body
        assert mock.last_model == "model-solo"

        assistant_message = (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .one()
        )
        assert db_session.query(MaxModeCandidate).filter(
            MaxModeCandidate.message_id == assistant_message.id
        ).count() == 0
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_conversation_update_can_toggle_max_mode(client):
    token = _register_and_login(client, "toggle-max@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    conv = client.post("/api/v1/conversations", json={}, headers=headers)
    conv_id = conv.json()["id"]
    assert conv.json()["max_mode_enabled"] is False

    updated = client.patch(f"/api/v1/conversations/{conv_id}", json={"max_mode_enabled": True}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["max_mode_enabled"] is True
