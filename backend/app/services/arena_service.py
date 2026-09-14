"""Model Arena (spec's "Video/Frontier Model Arena" idea, scoped to what's honestly runnable
here): run one admin-supplied prompt against every registered model for a capability side by
side, instead of benchmark_service's fixed prompt suite. Reuses benchmark_service's own
word-overlap scorer when the admin supplies a reference answer; otherwise leaves score null
for side-by-side human judgment, same honesty convention as run_benchmark returning an empty
list for capabilities without a defined suite."""
import asyncio
import time
import uuid

from sqlalchemy.orm import Session

from app.db.models.arena_comparison_result import ArenaComparisonResult
from app.db.models.model_registry import RegisteredModel
from app.services.benchmark_service import BenchmarkPrompt, score_response
from app.services.llm_provider import LLMProvider

# EXPERIMENTAL models are included (unlike the MAX-mode candidate pool in chat_service, which
# restricts to PRODUCTION/CANARY): the whole point of the arena is to let an admin evaluate an
# untested model before promoting it, not just compare already-trusted ones.
ARENA_STATUSES = ("PRODUCTION", "CANARY", "EXPERIMENTAL")


async def _run_one(
    llm_client: LLMProvider, model: RegisteredModel, prompt: str, reference_answer: str | None
) -> ArenaComparisonResult:
    start = time.monotonic()
    response = await llm_client.chat(model.base_model, [{"role": "user", "content": prompt}])
    latency_ms = int((time.monotonic() - start) * 1000)
    score = (
        score_response(BenchmarkPrompt("arena", prompt, reference_answer=reference_answer), response)
        if reference_answer
        else None
    )
    return ArenaComparisonResult(
        model_id=model.id,
        capability=model.capability,
        prompt=prompt,
        response=response,
        score=score,
        latency_ms=latency_ms,
    )


async def run_arena_comparison(
    db: Session,
    llm_client: LLMProvider,
    capability: str,
    prompt: str,
    reference_answer: str | None = None,
) -> list[ArenaComparisonResult]:
    candidates = (
        db.query(RegisteredModel)
        .filter(
            RegisteredModel.provider == "LOCAL",
            RegisteredModel.capability == capability,
            RegisteredModel.status.in_(ARENA_STATUSES),
        )
        .order_by(RegisteredModel.eval_score.desc().nullslast(), RegisteredModel.created_at.asc())
        .all()
    )
    if not candidates:
        return []

    comparison_id = uuid.uuid4()
    results = await asyncio.gather(*(_run_one(llm_client, model, prompt, reference_answer) for model in candidates))
    for result in results:
        result.comparison_id = comparison_id

    db.add_all(results)
    db.commit()
    for row in results:
        db.refresh(row)

    return list(results)


def list_arena_history(db: Session, capability: str | None = None, limit: int = 50) -> list[ArenaComparisonResult]:
    query = db.query(ArenaComparisonResult)
    if capability:
        query = query.filter(ArenaComparisonResult.capability == capability)
    return query.order_by(ArenaComparisonResult.created_at.desc()).limit(limit).all()
