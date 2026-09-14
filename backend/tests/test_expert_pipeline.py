import pytest

from app.core.config import get_settings
from app.db.models.conversation import Conversation
from app.db.models.expert_pipeline_step import ExpertPipelineStep
from app.db.models.message import Message
from app.main import app
from app.services.expert_pipeline_service import (
    ExpertPipelineError,
    _generate_plan,
    run_expert_pipeline,
)
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider

settings = get_settings()

_VALID_PLAN = (
    '```expert-plan\n{"steps": [{"step_type": "REASONING", "instruction": "explain X"}, '
    '{"step_type": "CODING", "instruction": "write Y"}]}\n```'
)


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


# --- _generate_plan -------------------------------------------------------------------------


async def test_generate_plan_parses_valid_block(db_session):
    mock = MockProvider(reply=_VALID_PLAN)
    plan = await _generate_plan(mock, "planner-model", "do something complex", tools_enabled=False, max_steps=5, max_retries=1)
    assert [s.step_type for s in plan.steps] == ["REASONING", "CODING"]


async def test_generate_plan_rejects_tool_step_when_tools_disabled_and_retries(db_session):
    invalid = '```expert-plan\n{"steps": [{"step_type": "TOOL", "instruction": "calc"}]}\n```'
    mock = MockProvider(replies=[invalid, _VALID_PLAN])
    plan = await _generate_plan(mock, "planner-model", "do something", tools_enabled=False, max_steps=5, max_retries=1)
    assert [s.step_type for s in plan.steps] == ["REASONING", "CODING"]


async def test_generate_plan_raises_after_exhausting_retries(db_session):
    mock = MockProvider(reply="not a fenced block at all")
    with pytest.raises(ExpertPipelineError):
        await _generate_plan(mock, "planner-model", "do something", tools_enabled=False, max_steps=5, max_retries=1)


# --- run_expert_pipeline ---------------------------------------------------------------------


async def test_run_expert_pipeline_executes_verifies_and_synthesizes(db_session):
    mock = MockProvider(
        replies=[
            _VALID_PLAN,
            "reasoning raw output",  # step 1 execute
            "OK",  # step 1 verify (kept as-is)
            "def y(): pass",  # step 2 execute
            "corrected code",  # step 2 verify (replaces raw)
            "final combined answer",  # synthesis
        ]
    )

    final_answer, steps = await run_expert_pipeline(db_session, mock, "do something complex", tools_enabled=False)

    assert final_answer == "final combined answer"
    assert len(steps) == 2
    assert steps[0].step.step_type == "REASONING"
    assert steps[0].raw_output == "reasoning raw output"
    assert steps[0].verified_output == "reasoning raw output"  # "OK" -> unchanged
    assert steps[1].step.step_type == "CODING"
    assert steps[1].raw_output == "def y(): pass"
    assert steps[1].verified_output == "corrected code"  # not "OK" -> replaced
    assert steps[1].model == settings.ollama_code_model


async def test_run_expert_pipeline_propagates_planner_failure(db_session):
    mock = MockProvider(reply="never a valid plan")
    with pytest.raises(ExpertPipelineError):
        await run_expert_pipeline(db_session, mock, "do something", tools_enabled=False)


# --- chat_service integration -----------------------------------------------------------------


def test_expert_pipeline_conversation_runs_and_persists_steps(client, db_session):
    mock = MockProvider(
        replies=[
            _VALID_PLAN,
            "reasoning raw output",
            "OK",
            "def y(): pass",
            "OK",
            "final combined answer",
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "expert-pipeline-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={"expert_pipeline_enabled": True}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "do something complex"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "expert_pipeline_steps" in body

        assistant_message = (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .one()
        )
        assert assistant_message.content == "final combined answer"

        steps = (
            db_session.query(ExpertPipelineStep)
            .filter(ExpertPipelineStep.message_id == assistant_message.id)
            .order_by(ExpertPipelineStep.step_index)
            .all()
        )
        assert [s.step_type for s in steps] == ["REASONING", "CODING"]

        listed = client.get(
            f"/api/v1/conversations/{conv_id}/messages/{assistant_message.id}/expert-pipeline-steps",
            headers=headers,
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 2
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_expert_pipeline_planner_failure_persists_no_message(client, db_session):
    mock = MockProvider(reply="never a valid plan")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "expert-pipeline-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={"expert_pipeline_enabled": True}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "error" in body

        assert (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .count()
            == 0
        )
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_conversation_create_rejects_both_reply_modes(client):
    token = _register_and_login(client, "both-modes@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        "/api/v1/conversations",
        json={"max_mode_enabled": True, "expert_pipeline_enabled": True},
        headers=headers,
    )
    assert resp.status_code == 400


def test_conversation_update_rejects_enabling_expert_pipeline_when_max_mode_already_on(client):
    token = _register_and_login(client, "toggle-conflict@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    conv = client.post("/api/v1/conversations", json={"max_mode_enabled": True}, headers=headers)
    conv_id = conv.json()["id"]

    resp = client.patch(f"/api/v1/conversations/{conv_id}", json={"expert_pipeline_enabled": True}, headers=headers)
    assert resp.status_code == 400
