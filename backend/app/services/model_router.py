"""FrontierModelRouter — resolves "I need a model with capability X" to a concrete
RegisteredModel, instead of the rest of the backend hardcoding a settings field per
capability.

Scoped to this deployment's reality: no cloud provider has an API key configured (an
explicit choice, not a gap — see the frontier-orchestration spec notes in project memory),
so every candidate the router can ever return has provider="LOCAL" today. `mode` is
accepted now so the API contract doesn't have to change when a second provider exists:

- AUTO: capability-based selection among PRODUCTION LOCAL models (the only real option today)
- PRIVATE: never leaves local hardware — identical to AUTO right now since nothing else
  exists yet, but the distinction becomes real the moment a cloud provider is added

FAST/BEST/CHEAP/MAXIMUM are deliberately not implemented: with a single provider tier they'd
be no-op aliases for AUTO, and pretending to differentiate would be dishonest. Add them once
there's more than one real candidate per capability to actually rank.
"""
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.model_registry import RegisteredModel

settings = get_settings()

VALID_MODES = ("AUTO", "PRIVATE")

_DEFAULT_MODEL_BY_CAPABILITY = {
    "TEXT": lambda s: s.ollama_model,
    "CODE": lambda s: s.ollama_code_model,
    "VISION": lambda s: s.ollama_vision_model,
    "EMBEDDING": lambda s: s.ollama_embedding_model,
}


class FrontierModelRouter:
    def select(self, db: Session, capability: str, mode: str = "AUTO") -> RegisteredModel:
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown routing mode {mode!r}; expected one of {VALID_MODES}")

        candidate = (
            db.query(RegisteredModel)
            .filter(
                RegisteredModel.status == "PRODUCTION",
                RegisteredModel.provider == "LOCAL",
                RegisteredModel.capability == capability,
            )
            .order_by(RegisteredModel.eval_score.desc().nullslast(), RegisteredModel.created_at.asc())
            .first()
        )
        if candidate is not None:
            return candidate

        return self._bootstrap_default(db, capability)

    def _bootstrap_default(self, db: Session, capability: str) -> RegisteredModel:
        """Nothing is registered for this capability yet — register the settings-configured
        default as PRODUCTION so routing never fails, and so the next call finds it directly
        without repeating this bootstrap. Self-healing: works even if the registry table was
        just created or was wiped."""
        resolver = _DEFAULT_MODEL_BY_CAPABILITY.get(capability)
        if resolver is None:
            raise ValueError(f"Unknown capability {capability!r}; expected one of {list(_DEFAULT_MODEL_BY_CAPABILITY)}")
        base_model = resolver(settings)

        existing = (
            db.query(RegisteredModel)
            .filter(RegisteredModel.provider == "LOCAL", RegisteredModel.base_model == base_model)
            .first()
        )
        if existing is not None:
            existing.status = "PRODUCTION"
            existing.capability = capability
            db.commit()
            db.refresh(existing)
            return existing

        entry = RegisteredModel(
            name=f"local-{base_model}",
            version="v1",
            base_model=base_model,
            capability=capability,
            provider="LOCAL",
            quantization=None,
            location=f"ollama://{base_model}",
            status="PRODUCTION",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry


def get_model_router() -> FrontierModelRouter:
    return FrontierModelRouter()
