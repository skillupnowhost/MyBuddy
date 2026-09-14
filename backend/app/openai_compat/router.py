import json
import time
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import get_current_user
from app.db.models.user import User
from app.schemas.chat import (
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
    OpenAIChoice,
    OpenAIChoiceMessage,
)
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider

router = APIRouter(tags=["openai-compatible"])


async def _stream_openai_chunks(
    completion_id: str,
    model: str,
    llm_client: LLMProvider,
    messages: list[dict],
    temperature: float,
) -> AsyncGenerator[str, None]:
    created = int(time.time())
    async for delta in llm_client.chat_stream(model, messages, temperature):
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"

    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: OpenAIChatCompletionRequest,
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    messages = [m.model_dump() for m in payload.messages]

    if payload.stream:
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        return StreamingResponse(
            _stream_openai_chunks(completion_id, payload.model, llm_client, messages, payload.temperature),
            media_type="text/event-stream",
        )

    content = await llm_client.chat(payload.model, messages, payload.temperature)
    return OpenAIChatCompletionResponse(
        model=payload.model,
        choices=[OpenAIChoice(message=OpenAIChoiceMessage(content=content))],
    )
