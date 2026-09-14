from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.models.user import User
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider

settings = get_settings()
router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    return {
        "models": await llm_client.list_models(),
        "default_model": settings.ollama_model,
        "code_model": settings.ollama_code_model,
    }
