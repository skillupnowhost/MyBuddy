from sqlalchemy.orm import Session

from app.db.models.model_registry import RegisteredModel
from app.services.llm_provider import LLMProvider

# Substring hints used to guess a capability for a model Ollama already has installed,
# so discovery doesn't require the user to hand-classify every model. Order matters:
# checked top to bottom, first match wins. Anything unmatched defaults to TEXT.
CAPABILITY_HINTS: list[tuple[str, str]] = [
    ("coder", "CODE"),
    ("code", "CODE"),
    ("moondream", "VISION"),
    ("llava", "VISION"),
    ("bakllava", "VISION"),
    ("vision", "VISION"),
    ("minilm", "EMBEDDING"),
    ("embed", "EMBEDDING"),
    ("bge", "EMBEDDING"),
    ("nomic", "EMBEDDING"),
]


def guess_capability(model_name: str) -> str:
    lowered = model_name.lower()
    for hint, capability in CAPABILITY_HINTS:
        if hint in lowered:
            return capability
    return "TEXT"


async def discover_local_models(db: Session, llm_client: LLMProvider) -> list[RegisteredModel]:
    """Scans what's actually installed in the local Ollama server and registers anything not
    already known as a base model (spec's Model Discovery Engine, honestly scoped to local
    Ollama only — no HuggingFace/registry scanning, since no online discovery is in scope).
    Registers new entries as EXPERIMENTAL — an admin must promote them before the router will
    ever select one. Idempotent: already-known base models (by base_model name) are skipped."""
    installed = await llm_client.list_models()

    known = {
        row.base_model
        for row in db.query(RegisteredModel)
        .filter(RegisteredModel.provider == "LOCAL", RegisteredModel.training_job_id.is_(None))
        .all()
    }

    newly_registered: list[RegisteredModel] = []
    for model_name in installed:
        if model_name in known:
            continue
        entry = RegisteredModel(
            name=f"local-{model_name}",
            version="v1",
            base_model=model_name,
            capability=guess_capability(model_name),
            provider="LOCAL",
            quantization=None,
            location=f"ollama://{model_name}",
            status="EXPERIMENTAL",
        )
        db.add(entry)
        newly_registered.append(entry)

    if newly_registered:
        db.commit()
        for entry in newly_registered:
            db.refresh(entry)

    return newly_registered
