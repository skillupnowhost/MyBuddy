import json
import uuid

import pytest

from app.core.config import get_settings
from app.db.models.agent_step import AgentStep
from app.db.models.code_file import CodeFile
from app.db.models.code_project import CodeProject
from app.db.models.memory import Memory
from app.db.models.message import Message
from app.main import app
from app.services.agent_service import MAX_AGENT_STEPS, run_agent_loop
from app.services.llm_client import get_llm_client
from app.services.mock_provider import MockProvider
from app.services.tools import TOOL_REGISTRY, ToolContext, maybe_run_tool_call
from app.services.tools.read_code_file import ReadCodeFileTool
from app.services.tools.search_memories import SearchMemoriesTool

settings = get_settings()


def _register_and_login(client, email, password="supersecret123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _tool_call_reply(tool: str, args: dict) -> str:
    return f'```tool\n{json.dumps({"tool": tool, "args": args})}\n```'


# --- read_code_file tool --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_code_file_requires_context(db_session):
    tool = ReadCodeFileTool()
    assert await tool.run({"project_id": "x", "path": "a.py"}) == "Error: this tool requires an authenticated context."


@pytest.mark.asyncio
async def test_read_code_file_rejects_other_users_project(db_session, tmp_path):
    owner_id = uuid.uuid4()
    intruder_id = uuid.uuid4()
    project = CodeProject(
        id=uuid.uuid4(), user_id=owner_id, name="proj", storage_dir=str(tmp_path), status="READY"
    )
    db_session.add(project)
    db_session.commit()

    tool = ReadCodeFileTool()
    result = await tool.run(
        {"project_id": str(project.id), "path": "a.py"}, ToolContext(db=db_session, user_id=intruder_id)
    )
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_read_code_file_reads_owned_file(db_session, tmp_path):
    user_id = uuid.uuid4()
    file_path = tmp_path / "a.py"
    file_path.write_text("print('hi')")

    project = CodeProject(id=uuid.uuid4(), user_id=user_id, name="proj", storage_dir=str(tmp_path), status="READY")
    db_session.add(project)
    db_session.commit()
    db_session.add(
        CodeFile(project_id=project.id, relative_path="a.py", storage_path=str(file_path), size_bytes=12)
    )
    db_session.commit()

    tool = ReadCodeFileTool()
    result = await tool.run({"project_id": str(project.id), "path": "a.py"}, ToolContext(db=db_session, user_id=user_id))
    assert result == "print('hi')"


@pytest.mark.asyncio
async def test_read_code_file_missing_file_in_owned_project(db_session, tmp_path):
    user_id = uuid.uuid4()
    project = CodeProject(id=uuid.uuid4(), user_id=user_id, name="proj", storage_dir=str(tmp_path), status="READY")
    db_session.add(project)
    db_session.commit()

    tool = ReadCodeFileTool()
    result = await tool.run(
        {"project_id": str(project.id), "path": "missing.py"}, ToolContext(db=db_session, user_id=user_id)
    )
    assert "not found" in result.lower()


# --- search_memories tool -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_memories_requires_context(db_session):
    tool = SearchMemoriesTool()
    assert await tool.run({"query": "x"}) == "Error: this tool requires an authenticated context."


@pytest.mark.asyncio
async def test_search_memories_finds_own_matches_only(db_session):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    db_session.add_all(
        [
            Memory(user_id=owner_id, content="likes pizza", source="manual"),
            Memory(user_id=owner_id, content="works remotely", source="manual"),
            Memory(user_id=other_id, content="also likes pizza", source="manual"),
        ]
    )
    db_session.commit()

    tool = SearchMemoriesTool()
    result = await tool.run({"query": "pizza"}, ToolContext(db=db_session, user_id=owner_id))
    assert "likes pizza" in result
    assert "works remotely" not in result
    assert "also likes pizza" not in result


@pytest.mark.asyncio
async def test_search_memories_no_match(db_session):
    user_id = uuid.uuid4()
    tool = SearchMemoriesTool()
    result = await tool.run({"query": "nonexistent"}, ToolContext(db=db_session, user_id=user_id))
    assert result == "No matching memories found."


def test_new_tools_registered():
    assert "read_code_file" in TOOL_REGISTRY
    assert "search_memories" in TOOL_REGISTRY


# --- run_agent_loop --------------------------------------------------------------------------


async def test_agent_loop_returns_direct_answer_with_no_tool_calls(db_session):
    mock = MockProvider(reply="just a direct answer")
    final, steps = await run_agent_loop(db_session, mock, "some-model", [{"role": "user", "content": "hi"}], uuid.uuid4())
    assert final == "just a direct answer"
    assert steps == []


async def test_agent_loop_chains_multiple_tool_calls_then_answers(db_session):
    replies = [
        _tool_call_reply("calculator", {"expression": "2 + 2"}),
        _tool_call_reply("current_datetime", {}),
        "final answer using both results",
    ]
    mock = MockProvider(replies=replies)
    final, steps = await run_agent_loop(db_session, mock, "some-model", [{"role": "user", "content": "hi"}], uuid.uuid4())

    assert final == "final answer using both results"
    assert len(steps) == 2
    assert steps[0].tool_name == "calculator"
    assert steps[0].tool_result == "4"
    assert steps[1].tool_name == "current_datetime"


async def test_agent_loop_stops_at_step_cap(db_session):
    # The model always calls the calculator, never gives a final answer -> loop must not hang.
    looping_reply = _tool_call_reply("calculator", {"expression": "1 + 1"})
    mock = MockProvider(replies=[looping_reply] * MAX_AGENT_STEPS + ["forced final answer"])
    final, steps = await run_agent_loop(db_session, mock, "some-model", [{"role": "user", "content": "hi"}], uuid.uuid4())

    assert len(steps) == MAX_AGENT_STEPS
    assert final == "forced final answer"


# --- chat_service integration -----------------------------------------------------------------


def test_agent_mode_conversation_chains_tools_and_persists_steps(client, db_session):
    replies = [
        _tool_call_reply("calculator", {"expression": "6 * 7"}),
        "the answer is 42",
    ]
    mock = MockProvider(replies=replies)
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "agent-mode-user@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={"agent_mode_enabled": True}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "what is 6*7?"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "agent_tools_used" in body

        assistant_message = (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .one()
        )
        assert assistant_message.content == "the answer is 42"

        steps = db_session.query(AgentStep).filter(AgentStep.message_id == assistant_message.id).all()
        assert len(steps) == 1
        assert steps[0].tool_name == "calculator"
        assert steps[0].tool_result == "42"

        listed = client.get(
            f"/api/v1/conversations/{conv_id}/messages/{assistant_message.id}/agent-steps", headers=headers
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_agent_mode_direct_answer_persists_no_steps(client, db_session):
    mock = MockProvider(reply="just answering directly, no tools needed")
    app.dependency_overrides[get_llm_client] = lambda: mock
    try:
        token = _register_and_login(client, "agent-mode-direct@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        conv = client.post("/api/v1/conversations", json={"agent_mode_enabled": True}, headers=headers)
        conv_id = conv.json()["id"]

        with client.stream(
            "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "hi"}, headers=headers
        ) as resp:
            body = "".join(resp.iter_text())
        assert "agent_tools_used" not in body

        assistant_message = (
            db_session.query(Message)
            .filter(Message.conversation_id == conv_id, Message.role == "assistant")
            .one()
        )
        assert db_session.query(AgentStep).filter(AgentStep.message_id == assistant_message.id).count() == 0
    finally:
        app.dependency_overrides.pop(get_llm_client, None)


def test_conversation_create_rejects_agent_mode_with_max_mode(client):
    token = _register_and_login(client, "agent-conflict-max@example.com")
    resp = client.post(
        "/api/v1/conversations",
        json={"max_mode_enabled": True, "agent_mode_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_conversation_create_rejects_agent_mode_with_expert_pipeline(client):
    token = _register_and_login(client, "agent-conflict-expert@example.com")
    resp = client.post(
        "/api/v1/conversations",
        json={"expert_pipeline_enabled": True, "agent_mode_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
