import asyncio
import base64
import json
import uuid
from collections.abc import AsyncGenerator, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.conversation import Conversation
from app.db.models.image import Image
from app.db.models.max_mode_candidate import MaxModeCandidate
from app.db.models.message import Message
from app.db.models.model_registry import RegisteredModel
from app.db.models.usage_log import UsageLog
from app.services.code_rag_service import build_code_rag_prompt, retrieve_code_context
from app.services.code_vector_store import CodeVectorStoreProvider
from app.services.embedding_provider import EmbeddingProvider
from app.services.llm_provider import LLMProvider
from app.services.max_mode_service import (
    MaxModeCandidateResult,
    generate_max_mode_reply,
    get_max_mode_candidates,
)
from app.services.memory_service import extract_and_save_memories, get_memory_context
from app.services.model_router import get_model_router
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


def _chunk_text(text: str, size: int = 40) -> list[str]:
    """MAX mode returns its synthesized reply all at once (it's not token-streamed like a
    normal chat_stream call — the judge call itself is non-streaming), so this re-chunks it
    into small pieces purely so the SSE 'delta' protocol still animates in the frontend the
    same way a normal reply does, instead of dumping one giant delta."""
    return [text[i : i + size] for i in range(0, len(text), size)]


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
    image_ids: list[uuid.UUID] | None = None,
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

        attached_images: list[Image] = []
        for image_id in image_ids or []:
            image = db.get(Image, image_id)
            if image is not None and image.user_id == conversation.user_id:
                image.message_id = user_message.id
                attached_images.append(image)
        if attached_images:
            db.commit()

        db.refresh(conversation)

        capability = "CODE" if conversation.code_project_id else "TEXT"
        max_mode_candidates: list[RegisteredModel] = []
        if attached_images:
            # A pinned conversation.model can't see images (most local models aren't
            # vision-capable) — vision must override the pin, same as before this router
            # existed, not just apply when nothing is pinned. MAX mode doesn't cover image
            # turns for v1 (fan-out cost doubles per image, no judge-of-images story yet) —
            # always falls back to the single VISION model here.
            model = get_model_router().select(db, "VISION").base_model
        else:
            if conversation.max_mode_enabled:
                max_mode_candidates = get_max_mode_candidates(db, capability)
            if len(max_mode_candidates) >= 2:
                # MAX mode takes priority over a pinned conversation.model when active — its
                # whole point is fanning out to multiple models, not honoring a single pin.
                # `model` is resolved after generation, to the judge model, for usage/memory
                # attribution — see the generation block below.
                model = None
            elif conversation.model:
                model = conversation.model
            else:
                model = get_model_router().select(db, capability).base_model
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

        if attached_images and history:
            # A sibling key on the message dict, not a content rewrite — composes cleanly
            # with the RAG branches above, which only ever replace `content`.
            encoded = []
            for image in attached_images:
                with open(image.storage_path, "rb") as f:
                    encoded.append(base64.b64encode(f.read()).decode("ascii"))
            history[-1]["images"] = encoded

        usage_sink: dict = {}
        full_reply = ""
        max_mode_results: list[MaxModeCandidateResult] = []
        try:
            if len(max_mode_candidates) >= 2:
                full_reply, max_mode_results = await generate_max_mode_reply(llm_client, history, max_mode_candidates)
                model = max_mode_results[-1].model.base_model  # the judge, for usage/memory attribution
                yield f"data: {json.dumps({'max_mode_models': [r.model.base_model for r in max_mode_results]})}\n\n"
                for chunk in _chunk_text(full_reply):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                # Tool-calling on top of a MAX-mode synthesized reply is explicitly out of
                # scope for v1 — the tool-call convention expects a single model's raw
                # fenced-block output, not a judge's prose synthesis — so MAX-mode
                # conversations skip the tools_enabled branch entirely.
            else:
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
                if max_mode_results:
                    db.add_all(
                        [
                            MaxModeCandidate(
                                message_id=assistant_message.id,
                                model_id=r.model.id,
                                base_model=r.model.base_model,
                                response=r.response,
                                latency_ms=r.latency_ms,
                                is_judge=r.is_judge,
                            )
                            for r in max_mode_results
                        ]
                    )
                    db.commit()
                else:
                    _log_usage(db, conversation.user_id, model, usage_sink)
                asyncio.create_task(
                    extract_and_save_memories(
                        session_factory, llm_client, model, conversation.user_id, user_content, full_reply
                    )
                )

        yield f"data: {json.dumps({'done': True})}\n\n"
    finally:
        db.close()
