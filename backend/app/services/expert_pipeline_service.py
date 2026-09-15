"""Expert Model Collaboration Pipeline (spec's Planner -> Reasoning/Coding/Tool -> Verification
-> Synthesizer idea, phase 9 sub-phase 4). Honestly scoped to this deployment's reality:
there's no dedicated "reasoning" model distinct from TEXT, so the Planner, REASONING steps,
Verification, and the Synthesizer all route through the TEXT capability's top-ranked model
(via FrontierModelRouter) — only CODING steps get a distinct model (the CODE capability). A
Vision Agent stage is out of scope for v1 (the pipeline has no image input — see chat_service,
which never activates it for a turn with attached images) and the "Tool Agent" stage reuses
the existing Tool system (app/services/tools) rather than inventing a second one.

Steps run sequentially, not fanned out like MAX mode: each step is meant to be independent
(the planner is told to write self-contained instructions), but this deployment has one
CPU-only local inference backend, and running several steps concurrently against it would
just contend for the same resource, not actually parallelize — so sequential execution is the
honest choice here, not a missing optimization.
"""
import json
import re
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.services.llm_provider import LLMProvider
from app.services.model_router import get_model_router
from app.services.tools import ToolContext, get_current_datetime_context, get_tools_system_prompt, maybe_run_tool_call

VALID_STEP_TYPES = ("REASONING", "CODING", "TOOL")

_PLAN_BLOCK_RE = re.compile(r"```expert-plan\s*\n(.*?)\n```", re.DOTALL)

_PLANNER_SYSTEM_PROMPT = """You are a planning assistant. Break the user's request into an \
ordered list of 1-{max_steps} small subtasks for a team of specialist AI models to execute; \
a synthesizer will then combine their answers into one final reply. Respond with ONLY a \
fenced block in exactly this format (no other text):
```expert-plan
{{"steps": [{{"step_type": "REASONING", "instruction": "..."}}]}}
```
step_type must be one of:
- REASONING: general reasoning, analysis, writing, explanation — no code involved
- CODING: writing, fixing, or reviewing code
{tool_line}
Each instruction must be self-contained (the specialist model only sees that one instruction, \
not the rest of the conversation). Do not over-decompose a simple request — use as few steps \
as it actually needs, often just 1."""


class PlanStep(BaseModel):
    step_type: str
    instruction: str


class _PlanResponse(BaseModel):
    steps: list[PlanStep]


class ExpertPipelineError(Exception):
    """Raised when the planner can't be coaxed into a valid plan within the retry budget —
    the caller must surface this clearly, never silently fall back to a single-model reply."""


@dataclass
class ExpertStepResult:
    step: PlanStep
    model: str
    raw_output: str
    verified_output: str


async def _generate_plan(
    llm_client: LLMProvider, model: str, user_content: str, tools_enabled: bool, max_steps: int, max_retries: int
) -> _PlanResponse:
    tool_line = "- TOOL: needs a tool call (e.g. a calculation or the current date/time)" if tools_enabled else ""
    allowed_types = VALID_STEP_TYPES if tools_enabled else ("REASONING", "CODING")
    system_prompt = _PLANNER_SYSTEM_PROMPT.format(max_steps=max_steps, tool_line=tool_line).rstrip()
    messages = [
        {"role": "system", "content": f"{get_current_datetime_context()}\n\n{system_prompt}"},
        {"role": "user", "content": user_content},
    ]

    last_error: str | None = None
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```expert-plan block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _PLAN_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```expert-plan fenced block found"
            continue
        try:
            plan = _PlanResponse.model_validate(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        if not plan.steps:
            last_error = "steps must not be empty"
            continue
        if len(plan.steps) > max_steps:
            last_error = f"too many steps ({len(plan.steps)} > {max_steps})"
            continue
        bad_steps = [s for s in plan.steps if s.step_type not in allowed_types]
        if bad_steps:
            last_error = f"step_type must be one of {allowed_types}, got {bad_steps[0].step_type!r}"
            continue

        return plan

    raise ExpertPipelineError(
        f"The planner could not produce a valid plan after {max_retries + 1} attempt(s): {last_error}"
    )


async def _execute_step(
    db: Session, llm_client: LLMProvider, step: PlanStep, tools_enabled: bool, user_id: uuid.UUID
) -> tuple[str, str]:
    if step.step_type == "CODING":
        model = get_model_router().select(db, "CODE").base_model
    else:
        model = get_model_router().select(db, "TEXT").base_model

    if step.step_type == "TOOL" and tools_enabled:
        messages = [
            {"role": "system", "content": f"{get_current_datetime_context()}\n\n{get_tools_system_prompt()}"},
            {"role": "user", "content": step.instruction},
        ]
        reply = await llm_client.chat(model, messages)
        tool_result = await maybe_run_tool_call(reply, ToolContext(db=db, user_id=user_id))
        if tool_result is not None:
            reply = f"{reply}\n[Tool result: {tool_result.result}]"
        return model, reply

    messages = [
        {"role": "system", "content": get_current_datetime_context()},
        {"role": "user", "content": step.instruction},
    ]
    reply = await llm_client.chat(model, messages)
    return model, reply


async def _verify_step(llm_client: LLMProvider, model: str, step: PlanStep, output: str) -> str:
    prompt = (
        f"Instruction given to a specialist model:\n{step.instruction}\n\n"
        f"Its answer:\n{output}\n\n"
        "Check the answer for correctness and completeness against the instruction. If it is "
        "correct and complete, reply with exactly: OK\n"
        "If it has a real problem, reply with ONLY a corrected answer (no explanation of what "
        "changed)."
    )
    reply = await llm_client.chat(model, [{"role": "user", "content": prompt}])
    return output if reply.strip() == "OK" else reply


async def _synthesize(llm_client: LLMProvider, model: str, user_content: str, steps: list[ExpertStepResult]) -> str:
    steps_block = "\n\n".join(
        f"Subtask {i + 1} ({s.step.step_type}): {s.step.instruction}\nResult: {s.verified_output}"
        for i, s in enumerate(steps)
    )
    prompt = (
        "You are synthesizing a final answer from a team of specialist models that each "
        "handled one subtask of the user's original request. Combine their results into one "
        "clear, direct answer to the user — do not mention subtasks, models, or the planning "
        f"process.\n\nOriginal user request:\n{user_content}\n\nSubtask results:\n{steps_block}"
    )
    return await llm_client.chat(model, [{"role": "user", "content": prompt}])


async def run_expert_pipeline(
    db: Session,
    llm_client: LLMProvider,
    user_content: str,
    tools_enabled: bool,
    user_id: uuid.UUID,
    max_steps: int = 5,
    max_retries: int = 1,
) -> tuple[str, list[ExpertStepResult]]:
    planner_model = get_model_router().select(db, "TEXT").base_model
    plan = await _generate_plan(llm_client, planner_model, user_content, tools_enabled, max_steps, max_retries)

    steps: list[ExpertStepResult] = []
    for plan_step in plan.steps:
        model, raw_output = await _execute_step(db, llm_client, plan_step, tools_enabled, user_id)
        verified_output = await _verify_step(llm_client, planner_model, plan_step, raw_output)
        steps.append(ExpertStepResult(step=plan_step, model=model, raw_output=raw_output, verified_output=verified_output))

    final_answer = await _synthesize(llm_client, planner_model, user_content, steps)
    return final_answer, steps
