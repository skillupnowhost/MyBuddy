"""MAX mode (spec's "fan out to multiple models independently, judge, synthesize" idea,
phase 9 sub-phase 3): only meaningful once more than one model is registered PRODUCTION/CANARY
for a capability — with a single local model (this deployment's default), MAX mode is a
documented no-op that falls straight back to the normal one-model reply in
chat_service.stream_assistant_reply, same honest scope cut as FAST/BEST/CHEAP/MAXIMUM in
model_router.py.
"""
import asyncio
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.model_registry import RegisteredModel
from app.services.llm_provider import LLMProvider

# Only PRODUCTION/CANARY — unlike the arena (arena_service.py deliberately includes
# EXPERIMENTAL so an admin can evaluate untested models before trusting them), a live
# user-facing reply should never be synthesized from a model nobody has vetted yet.
MAX_MODE_STATUSES = ("PRODUCTION", "CANARY")


@dataclass
class MaxModeCandidateResult:
    model: RegisteredModel
    response: str
    latency_ms: int
    is_judge: bool = False


def get_max_mode_candidates(db: Session, capability: str) -> list[RegisteredModel]:
    return (
        db.query(RegisteredModel)
        .filter(
            RegisteredModel.provider == "LOCAL",
            RegisteredModel.capability == capability,
            RegisteredModel.status.in_(MAX_MODE_STATUSES),
        )
        .order_by(RegisteredModel.eval_score.desc().nullslast(), RegisteredModel.created_at.asc())
        .all()
    )


_SYNTHESIS_INSTRUCTIONS = (
    "You are synthesizing a single final answer from multiple AI models that independently "
    "answered the same user message. Read all candidate answers below, then reply with ONE "
    "best answer to the user's original message — combine their strengths, resolve any "
    "disagreement using your own judgment, and reply directly to the user (do not mention "
    "that this is a synthesis or refer to \"the candidates\")."
)


async def generate_max_mode_reply(
    llm_client: LLMProvider, history: list[dict], candidates: list[RegisteredModel]
) -> tuple[str, list[MaxModeCandidateResult]]:
    """Calls every candidate model with the same conversation history, then uses the
    highest-ranked candidate (candidates[0], per get_max_mode_candidates' ordering) as judge
    to synthesize one final reply. Returns the synthesized text plus every candidate's raw
    answer — judge's own first-pass answer included — for transparency/persistence."""

    async def _call(model: RegisteredModel) -> MaxModeCandidateResult:
        start = time.monotonic()
        response = await llm_client.chat(model.base_model, history)
        latency_ms = int((time.monotonic() - start) * 1000)
        return MaxModeCandidateResult(model=model, response=response, latency_ms=latency_ms)

    candidate_results = list(await asyncio.gather(*(_call(model) for model in candidates)))

    judge = candidates[0]
    user_message = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    candidates_block = "\n\n".join(
        f"Candidate {i + 1} ({r.model.base_model}):\n{r.response}" for i, r in enumerate(candidate_results)
    )
    synthesis_prompt = (
        f"{_SYNTHESIS_INSTRUCTIONS}\n\nOriginal user message:\n{user_message}\n\n"
        f"Candidate answers:\n{candidates_block}"
    )
    start = time.monotonic()
    synthesized = await llm_client.chat(judge.base_model, [{"role": "user", "content": synthesis_prompt}])
    judge_latency_ms = int((time.monotonic() - start) * 1000)

    all_results = candidate_results + [
        MaxModeCandidateResult(model=judge, response=synthesized, latency_ms=judge_latency_ms, is_judge=True)
    ]
    return synthesized, all_results
