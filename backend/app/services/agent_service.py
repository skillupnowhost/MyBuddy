"""Bounded Agent Orchestration (phase 9 sub-phase 6): lets the model call tools repeatedly in
a loop instead of at most once per turn, up to a hard step cap, then gives a final answer.
Scope explicitly confirmed with the user before building this: a bounded loop over the
existing tool registry (calculator, current_datetime) plus two new READ-ONLY, ownership-
scoped tools (read_code_file, search_memories) — no writes, no network access, no arbitrary
code execution, and deliberately no generic/free-form database query tool (see
tools/search_memories.py's docstring for why). This is a real capability/safety jump from the
Tool system's original one-call-per-turn design, which is why it's its own opt-in
conversation mode (agent_mode_enabled) rather than a change to that existing behavior.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.llm_provider import LLMProvider
from app.services.tools import ToolContext, maybe_run_tool_call

MAX_AGENT_STEPS = 5

_STEP_LIMIT_PROMPT = (
    "You've reached the tool-call step limit for this turn. Give your best final answer now "
    "based on what you've learned so far, without using any more tools."
)


@dataclass
class AgentStepResult:
    """Named to avoid colliding with the persisted db.models.agent_step.AgentStep row —
    same naming convention as expert_pipeline_service.ExpertStepResult vs. ExpertPipelineStep."""

    assistant_reply: str
    tool_name: str
    tool_result: str


async def run_agent_loop(
    db: Session, llm_client: LLMProvider, model: str, history: list[dict], user_id: uuid.UUID
) -> tuple[str, list[AgentStepResult]]:
    """`history` must already include the tools system prompt (see chat_service, which adds
    it whenever tools_enabled OR agent_mode_enabled). Runs the model against a growing
    conversation, executing at most MAX_AGENT_STEPS tool calls before forcing a final answer
    — a runaway loop (the model repeatedly reaching for a tool instead of answering) always
    terminates, it just terminates with whatever the model has by then rather than hanging."""
    context = ToolContext(db=db, user_id=user_id)
    working_history = list(history)
    steps: list[AgentStepResult] = []

    for _ in range(MAX_AGENT_STEPS):
        reply = await llm_client.chat(model, working_history)
        tool_result = await maybe_run_tool_call(reply, context)
        if tool_result is None:
            return reply, steps

        steps.append(
            AgentStepResult(assistant_reply=reply, tool_name=tool_result.tool_name, tool_result=tool_result.result)
        )
        working_history.append({"role": "assistant", "content": reply})
        working_history.append({"role": "user", "content": f"[Tool result: {tool_result.result}]"})

    working_history.append({"role": "user", "content": _STEP_LIMIT_PROMPT})
    final_reply = await llm_client.chat(model, working_history)
    return final_reply, steps
