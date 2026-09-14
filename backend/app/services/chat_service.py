import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.usage_log import UsageLog
from app.services.code_rag_service import build_code_rag_prompt, retrieve_code_context
from app.services.code_vector_store import CodeVectorStoreProvider
from app.services.embedding_provider import EmbeddingProvider
from app.services.llm_provider import LLMProvider
from app.services.memory_service import extract_and_save_memories, get_memory_context
from app.services.rag_service import build_rag_prompt, retrieve_context
from app.services.tools import get_tools_system_prompt, maybe_run_tool_call
from app.services.vector_store import VectorStoreProvider

settings = get_settings()


def _history_for_ollama(conversation: Conversation, memory_context: str | None) -> list[dict]:
    history = []
    system_parts = []
    if conversation.system_prompt:
        system_parts.append(conversation.system_prompt)
    if memory_context:
        system_parts.append(memory_context)
    if conversation.tools_enabled:
        system_parts.append(get_tools_system_prompt())
    if system_parts:
        history.append({"role": "system", "content": "\n\n".join(system_parts)})
    for msg in conversation.messages:
        history.append({"role": msg.role, "content": msg.content})
    return history


def _log_usage(db: Session, user_id: uuid.UUID, model: str, usage_sink: dict) -> None:
    if not usage_sink:
        return
    db.add(
        UsageLog(
            user_id=user_id,
            model=model,
            prompt_tokens=usage_sink.get("prompt_tokens"),
            completion_tokens=usage_sink.get("completion_tokens"),
            duration_ms=usage_sink.get("duration_ms"),
        )
    )
    db.commit()


async def stream_assistant_reply(
    conversation_id: uuid.UUID,
    user_content: str,
    llm_client: LLMProvider,
    session_factory: Callable[[], Session],
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStoreProvider,
    code_vector_store: CodeVectorStoreProvider,
) -> AsyncGenerator[str, None]:
    """Persists the user message, streams the real model reply as SSE, then persists it.

    Opens its own DB session rather than reusing the request-scoped one: FastAPI tears down
    `Depends(get_db)` as soon as the endpoint function returns, which happens before a
    StreamingResponse's body iterator actually runs.
    """
    db = session_factory()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            yield f"data: {json.dumps({'error': 'Conversation not found'})}\n\n"
            return

        user_message = Message(conversation_id=conversation.id, role="user", content=user_content)
        db.add(user_message)
        db.commit()
        db.refresh(conversation)

        model = conversation.model or settings.ollama_model
        memory_context = get_memory_context(db, conversation.user_id)
        history = _history_for_ollama(conversation, memory_context)

        if conversation.code_project_id and history:
            # Code RAG is scoped to one open project and mutually exclusive with the
            # general document RAG below for v1 — mixing both retrieval sources into one
            # prompt is a v2 concern.
            code_chunks = await retrieve_code_context(
                db,
                conversation.user_id,
                conversation.code_project_id,
                user_content,
                embedding_provider,
                code_vector_store,
                settings.code_rag_top_k,
            )
            if code_chunks:
                history[-1] = {"role": "user", "content": build_code_rag_prompt(user_content, code_chunks)}
                sources = [
                    {
                        "filename": chunk.file.relative_path,
                        "page_number": None,
                        "lines": f"{chunk.start_line}-{chunk.end_line}" if chunk.start_line else None,
                    }
                    for chunk in code_chunks
                ]
                yield f"data: {json.dumps({'sources': sources})}\n\n"
        elif conversation.rag_enabled and history:
            chunks = await retrieve_context(
                db, conversation.user_id, user_content, embedding_provider, vector_store, settings.rag_top_k
            )
            if chunks:
                history[-1] = {"role": "user", "content": build_rag_prompt(user_content, chunks)}
                sources = [
                    {"filename": chunk.document.filename, "page_number": chunk.page_number} for chunk in chunks
                ]
                yield f"data: {json.dumps({'sources': sources})}\n\n"

        usage_sink: dict = {}
        full_reply = ""
        try:
            async for delta in llm_client.chat_stream(model, history, usage_sink=usage_sink):
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"

            if conversation.tools_enabled:
                tool_result = await maybe_run_tool_call(full_reply)
                if tool_result is not None:
                    yield f"data: {json.dumps({'tool_call': tool_result.tool_name})}\n\n"
                    history.append({"role": "assistant", "content": full_reply})
                    history.append({"role": "user", "content": f"[Tool result: {tool_result.result}]"})
                    full_reply = ""
                    async for delta in llm_client.chat_stream(model, history, usage_sink=usage_sink):
                        full_reply += delta
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
        finally:
            if full_reply:
                assistant_message = Message(conversation_id=conversation.id, role="assistant", content=full_reply)
                db.add(assistant_message)
                db.commit()
                _log_usage(db, conversation.user_id, model, usage_sink)
                asyncio.create_task(
                    extract_and_save_memories(
                        session_factory, llm_client, model, conversation.user_id, user_content, full_reply
                    )
                )

        yield f"data: {json.dumps({'done': True})}\n\n"
    finally:
        db.close()
