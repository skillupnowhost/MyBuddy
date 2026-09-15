import json
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models.memory import Memory
from app.services.llm_provider import LLMProvider

logger = logging.getLogger("mybuddy")

_MAX_MEMORIES_IN_CONTEXT = 20

_EXTRACTION_SYSTEM_PROMPT = (
    "You extract durable, long-term-worthy facts about a user from a single chat exchange. "
    "Durable means: still true and useful in a future, unrelated conversation (e.g. stated "
    "preferences, personal/project facts, recurring context). NOT durable: small talk, "
    "one-off questions, anything about the current task only. "
    "Respond with ONLY a JSON array of short strings, each one fact. If there is nothing "
    "durable worth remembering, respond with exactly: []"
)


def _dedupe_against_existing(candidates: list[str], existing: list[str]) -> list[str]:
    existing_lower = {e.strip().lower() for e in existing}
    return [c for c in candidates if c.strip() and c.strip().lower() not in existing_lower]


async def extract_and_save_memories(
    session_factory: Callable[[], Session],
    llm_client: LLMProvider,
    model: str,
    user_id: uuid.UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    """Best-effort: asks the model to extract durable facts from one exchange and saves any
    new ones. Runs as a fire-and-forget background task so it never adds latency to a chat
    response. Never raises — a failed extraction just means no memory gets saved this turn."""
    db = session_factory()
    try:
        prompt = [
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User said: {user_message}\n\nAssistant replied: {assistant_message}",
            },
        ]
        raw = await llm_client.chat(model, prompt, temperature=0.0)

        try:
            candidates = json.loads(raw.strip())
        except json.JSONDecodeError:
            # The model sometimes emits trailing prose, or even a second stray JSON value,
            # after the array we want. raw_decode parses only the first complete JSON value
            # and ignores everything after it, unlike a find("[")/rfind("]") slice — which
            # grabs the LAST "]" in the whole response and reproduces the exact same
            # "Extra data" failure when a second bracketed value follows the real one.
            start = raw.find("[")
            if start == -1:
                return
            try:
                candidates, _ = json.JSONDecoder().raw_decode(raw, start)
            except json.JSONDecodeError:
                return

        if not isinstance(candidates, list):
            return

        existing = [m.content for m in db.query(Memory).filter(Memory.user_id == user_id).all()]
        new_facts = _dedupe_against_existing([str(c) for c in candidates], existing)

        for fact in new_facts:
            db.add(Memory(user_id=user_id, content=fact.strip(), source="auto"))
        if new_facts:
            db.commit()
    except Exception:  # noqa: BLE001 - background best-effort extraction must never surface an error
        logger.exception("Memory extraction failed for user %s", user_id)
    finally:
        db.close()


def get_memory_context(db: Session, user_id: uuid.UUID) -> str | None:
    """Returns a system-prompt-ready block of the user's remembered facts, or None if empty."""
    memories = (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc())
        .limit(_MAX_MEMORIES_IN_CONTEXT)
        .all()
    )
    if not memories:
        return None

    facts = "\n".join(f"- {m.content}" for m in memories)
    return (
        "You have the following remembered facts about this user from past conversations. "
        "Use them only when relevant; do not force them into unrelated replies:\n"
        f"{facts}"
    )
