"""Model Benchmark Engine (spec's "AUTOMATIC EVALUATION" / "Quality Gate" idea, scoped to
what's honestly runnable on local hardware): a small, fixed, in-code prompt suite per
capability, scored without ever executing generated code — only the admin-gated sandbox
(see MyBuddy Code) is allowed to actually run untrusted code. Running the suite against a
RegisteredModel writes its average score to `eval_score`, which is exactly what
FrontierModelRouter already ranks candidates by (see model_router.py) — so a benchmark run
is what makes that ranking mean something instead of comparing NULLs.

VISION and EMBEDDING have no defined suite yet: scoring a vision reply or an embedding
vector against a fixed text reference isn't the same kind of problem as scoring a chat
reply, and building that honestly is a separate piece of work — run_benchmark returns an
empty list for those capabilities rather than pretending to score them.
"""
import re
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models.model_benchmark_result import ModelBenchmarkResult
from app.db.models.model_registry import RegisteredModel
from app.services.llm_provider import LLMProvider


@dataclass
class BenchmarkPrompt:
    prompt_id: str
    text: str
    reference_answer: str | None = None
    required_keywords: list[str] = field(default_factory=list)


BENCHMARK_PROMPTS: dict[str, list[BenchmarkPrompt]] = {
    "TEXT": [
        BenchmarkPrompt("text_arithmetic", "What is 12 plus 30? Answer with just the number.", reference_answer="42"),
        BenchmarkPrompt(
            "text_factual",
            "What is the capital of France? Answer with just the city name.",
            reference_answer="Paris",
        ),
        BenchmarkPrompt(
            "text_instruction_following",
            "Reply with exactly the word 'ready' and nothing else.",
            reference_answer="ready",
        ),
        BenchmarkPrompt(
            "text_formatting",
            "List three primary colors, one per line.",
            required_keywords=["red", "blue", "yellow"],
        ),
    ],
    "CODE": [
        BenchmarkPrompt(
            "code_write_function",
            "Write a Python function named add that returns the sum of two arguments.",
            required_keywords=["def add", "return"],
        ),
        BenchmarkPrompt(
            "code_fix_bug",
            "This Python function has a bug: `def double(x): return x + x + 1`. "
            "It should double its input. Reply with the corrected function only.",
            required_keywords=["def double", "x + x"],
        ),
        BenchmarkPrompt(
            "code_explain",
            "In one sentence, what does Python's `len()` function do?",
            required_keywords=["length"],
        ),
    ],
}


_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _word_overlap_f1(reference: str, response: str) -> float:
    ref_words = _words(reference)
    resp_words = _words(response)
    if not ref_words or not resp_words:
        return 0.0
    overlap = ref_words & resp_words
    if not overlap:
        return 0.0
    precision = len(overlap) / len(resp_words)
    recall = len(overlap) / len(ref_words)
    return 2 * precision * recall / (precision + recall)


def score_response(prompt: BenchmarkPrompt, response: str) -> float:
    if prompt.reference_answer is not None:
        return _word_overlap_f1(prompt.reference_answer, response)
    if prompt.required_keywords:
        lowered = response.lower()
        present = sum(1 for kw in prompt.required_keywords if kw.lower() in lowered)
        return present / len(prompt.required_keywords)
    return 0.0


async def run_benchmark(db: Session, llm_client: LLMProvider, model: RegisteredModel) -> list[ModelBenchmarkResult]:
    prompts = BENCHMARK_PROMPTS.get(model.capability)
    if not prompts:
        return []

    results: list[ModelBenchmarkResult] = []
    for prompt in prompts:
        start = time.monotonic()
        response = await llm_client.chat(model.base_model, [{"role": "user", "content": prompt.text}])
        latency_ms = int((time.monotonic() - start) * 1000)
        score = score_response(prompt, response)
        results.append(
            ModelBenchmarkResult(
                model_id=model.id,
                prompt_id=prompt.prompt_id,
                capability=model.capability,
                score=score,
                latency_ms=latency_ms,
                response_preview=response[:500],
            )
        )

    db.add_all(results)
    model.eval_score = sum(r.score for r in results) / len(results)
    db.commit()
    for row in results:
        db.refresh(row)

    return results
