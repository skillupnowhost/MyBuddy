import asyncio
import base64
import json
import uuid
from collections.abc import AsyncGenerator, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.agent_step import AgentStep
from app.db.models.conversation import Conversation
from app.db.models.expert_pipeline_step import ExpertPipelineStep
from app.db.models.image import Image
from app.db.models.max_mode_candidate import MaxModeCandidate
from app.db.models.message import Message
from app.db.models.model_registry import RegisteredModel
from app.db.models.usage_log import UsageLog
from app.services.agent_service import AgentStepResult, run_agent_loop
from app.services.code_execution_service import maybe_run_code_and_format_output
from app.services.code_rag_service import build_code_rag_prompt, retrieve_code_context
from app.services.code_vector_store import CodeVectorStoreProvider
from app.services.embedding_provider import EmbeddingProvider
from app.services.expert_pipeline_service import ExpertPipelineError, ExpertStepResult, run_expert_pipeline
from app.services.llm_provider import LLMProvider
from app.services.max_mode_service import (
    MaxModeCandidateResult,
    generate_max_mode_reply,
    get_max_mode_candidates,
)
from app.services.memory_service import extract_and_save_memories, get_memory_context
from app.services.model_router import get_model_router
from app.services.rag_service import build_rag_prompt, retrieve_context
from app.services.tools import (
    ToolContext,
    extract_explicit_image_request,
    get_current_datetime_context,
    get_tools_system_prompt,
    looks_like_tool_call_start,
    maybe_run_tool_call,
)
from app.services.vector_store import VectorStoreProvider

settings = get_settings()

# How many characters of a tool-enabled reply to hold back before showing anything, so
# "```tool" or a bare '{"tool"...' opening can be told apart from a normal answer (even one
# that starts with an ordinary code fence or a literal `{`) before any of it is displayed.
# Long enough to cover both prefixes with room for a little leading whitespace; short enough
# that a normal reply still feels like it's streaming live.
_TOOL_CALL_LOOKAHEAD_CHARS = 12

# Always-on, not tied to tools_enabled: a small local model left to its own defaults tends to
# wrap even a one-line request in unnecessary boilerplate (a function, a main() guard, an
# input() prompt) and to hand back code with no explanation of how it works — the opposite of
# what was asked for a "simple" snippet, and short of what a reference chat UI's code answers
# look like (code, then a plain-language walkthrough, then a sample run).
_CODE_ANSWER_STYLE = (
    "When your answer includes code: match the requested scope exactly — if asked for "
    "something simple, write the most direct version (no function wrapper, no main() guard, "
    "no input() prompt) unless one was actually requested, and honor every explicit detail in "
    "the request itself (e.g. 'with command line arguments' means read sys.argv/argparse, not "
    "input() or a hardcoded value — a stated requirement always overrides the simpler default). "
    "After the code, add a short 'How it works' section as a few bullet points walking through "
    "the key lines. Do not write your own 'Output' or example-run section — a real Python "
    "snippet is actually executed after you answer and its true output is appended "
    "automatically, so writing one yourself would only add a second, possibly wrong one. Skip "
    "this structure for one-line answers or questions that aren't about code."
)


def _history_for_ollama(conversation: Conversation, memory_context: str | None) -> list[dict]:
    history = []
    # Unconditional, not gated behind tools_enabled: no local model knows "right now" from
    # training regardless of how recently it was trained, and relying on the model to reliably
    # invoke the current_datetime tool (small models often don't emit the fenced-block call
    # correctly) is how "what's the date?" produced a hallucinated year.
    system_parts = [get_current_datetime_context(), _CODE_ANSWER_STYLE]
    if conversation.system_prompt:
        system_parts.append(conversation.system_prompt)
    if memory_context:
        system_parts.append(memory_context)
    if conversation.tools_enabled or conversation.agent_mode_enabled:
        system_parts.append(get_tools_system_prompt(code_project_active=bool(conversation.code_project_id)))
    if system_parts:
        history.append({"role": "system", "content": "\n\n".join(system_parts)})
    for msg in conversation.messages:
        history.append({"role": msg.role, "content": msg.content})
    return history


def _derive_title(user_content: str, max_len: int = 48) -> str:
    """First-message auto-title, so new conversations don't all sit in history as the same
    literal 'New conversation' string with nothing to tell them apart or search by."""
    collapsed = " ".join(user_content.split())
    if not collapsed:
        return "New conversation"
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[:max_len].rstrip() + "…"


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

        is_first_message = conversation.title == "New conversation" and not conversation.messages

        user_message = Message(conversation_id=conversation.id, role="user", content=user_content)
        db.add(user_message)
        db.commit()
        # The frontend only ever has a client-generated placeholder id for this message until
        # it hears this — needed so a later "edit and resend" can name the real row to delete
        # server-side instead of silently leaving a stale exchange behind.
        yield f"data: {json.dumps({'user_message_id': str(user_message.id)})}\n\n"

        if is_first_message:
            conversation.title = _derive_title(user_content)
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
        expert_pipeline_active = False
        agent_mode_active = False
        if attached_images:
            # A pinned conversation.model can't see images (most local models aren't
            # vision-capable) — vision must override the pin, same as before this router
            # existed, not just apply when nothing is pinned. None of MAX mode, the Expert
            # Pipeline, or Agent mode cover image turns for v1 (fan-out/sub-agent/tool-loop
            # cost doubles per image, no vision-agent story yet) — always falls back to the
            # single VISION model here.
            model = get_model_router().select(db, "VISION").base_model
        elif conversation.expert_pipeline_enabled:
            expert_pipeline_active = True
            model = None  # resolved after generation, to the planner/synthesizer model
        elif conversation.agent_mode_enabled:
            agent_mode_active = True
            model = get_model_router().select(db, capability).base_model
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
        expert_pipeline_steps: list[ExpertStepResult] = []
        agent_steps: list[AgentStepResult] = []
        generated_image_id: uuid.UUID | None = None
        try:
            if expert_pipeline_active:
                try:
                    full_reply, expert_pipeline_steps = await run_expert_pipeline(
                        db, llm_client, user_content, conversation.tools_enabled, conversation.user_id
                    )
                except ExpertPipelineError as exc:
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                else:
                    model = get_model_router().select(db, "TEXT").base_model  # planner/synthesizer, for attribution
                    yield (
                        "data: "
                        f"{json.dumps({'expert_pipeline_steps': [s.step.step_type for s in expert_pipeline_steps]})}"
                        "\n\n"
                    )
                    for chunk in _chunk_text(full_reply):
                        yield f"data: {json.dumps({'delta': chunk})}\n\n"
            elif agent_mode_active:
                full_reply, agent_steps = await run_agent_loop(db, llm_client, model, history, conversation.user_id)
                if agent_steps:
                    yield f"data: {json.dumps({'agent_tools_used': [s.tool_name for s in agent_steps]})}\n\n"
                for chunk in _chunk_text(full_reply):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
            elif len(max_mode_candidates) >= 2:
                full_reply, max_mode_results = await generate_max_mode_reply(llm_client, history, max_mode_candidates)
                model = max_mode_results[-1].model.base_model  # the judge, for usage/memory attribution
                yield f"data: {json.dumps({'max_mode_models': [r.model.base_model for r in max_mode_results]})}\n\n"
                for chunk in _chunk_text(full_reply):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                # Tool-calling on top of a MAX-mode synthesized reply is explicitly out of
                # scope for v1 — the tool-call convention expects a single model's raw
                # fenced-block output, not a judge's prose synthesis — so MAX-mode
                # conversations skip the tools_enabled branch entirely.
            elif conversation.tools_enabled:
                explicit_image_prompt = extract_explicit_image_request(user_content)
                if explicit_image_prompt is not None:
                    # An unmistakably-phrased image request — route straight to the tool
                    # rather than trust a (possibly small, local) model to notice and emit
                    # the fenced tool-call format on its own; see
                    # extract_explicit_image_request. Synthesizes exactly the reply a model
                    # that DID call the tool correctly would have produced, so everything
                    # below (tool_result handling, follow-up streaming, persistence) runs
                    # identically either way — this call is never itself shown to the user.
                    full_reply = (
                        "```tool\n"
                        + json.dumps({"tool": "generate_image", "args": {"prompt": explicit_image_prompt}})
                        + "\n```"
                    )
                    looks_like_tool_call = True
                else:
                    # A tool call is only ever valid as the model's ENTIRE first-pass reply
                    # (per the system prompt), so its opening characters give it away early.
                    # Hold back exactly that much before showing anything, so raw tool-call
                    # syntax — fenced, or on a small model that drops the fence, completely
                    # bare JSON — never flashes into the chat as if it were the answer (see
                    # looks_like_tool_call_start).
                    lookahead = ""
                    decided = False
                    showing = False
                    looks_like_tool_call = False
                    async for delta in llm_client.chat_stream(model, history, usage_sink=usage_sink):
                        full_reply += delta
                        if showing:
                            yield f"data: {json.dumps({'delta': delta})}\n\n"
                            continue
                        if decided:
                            # Decided, but not showing: this IS a tool-call attempt — keep
                            # silently buffering into full_reply (above) for the rest of this pass.
                            continue
                        lookahead += delta
                        if len(lookahead) < _TOOL_CALL_LOOKAHEAD_CHARS:
                            continue
                        decided = True
                        looks_like_tool_call = looks_like_tool_call_start(lookahead)
                        showing = not looks_like_tool_call
                        if showing:
                            yield f"data: {json.dumps({'delta': lookahead})}\n\n"
                    if not decided:
                        # Stream ended before the lookahead filled — too short to matter either
                        # way, so just show what came in.
                        looks_like_tool_call = looks_like_tool_call_start(lookahead)
                        if not looks_like_tool_call:
                            yield f"data: {json.dumps({'delta': lookahead})}\n\n"

                tool_result = await maybe_run_tool_call(full_reply, ToolContext(db=db, user_id=conversation.user_id))
                if tool_result is not None:
                    yield f"data: {json.dumps({'tool_call': tool_result.tool_name})}\n\n"
                    if tool_result.image_id is not None:
                        generated_image_id = tool_result.image_id
                        # Sent as soon as it's known so the frontend can render the image
                        # inline while the model is still streaming its follow-up reply, not
                        # only after a page reload re-fetches the persisted message.
                        yield f"data: {json.dumps({'image_id': str(tool_result.image_id)})}\n\n"
                    history.append({"role": "assistant", "content": full_reply})
                    history.append({"role": "user", "content": f"[Tool result: {tool_result.result}]"})
                    full_reply = ""
                    async for delta in llm_client.chat_stream(model, history, usage_sink=usage_sink):
                        full_reply += delta
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
                elif looks_like_tool_call:
                    # Looked like an attempted tool call (fenced or bare) but didn't resolve
                    # to a real one (malformed JSON, unknown tool name, ...) — show it rather
                    # than silently dropping the reply, which would look exactly like the "no
                    # response ever arrives" failure this whole flow exists to avoid.
                    for chunk in _chunk_text(full_reply):
                        yield f"data: {json.dumps({'delta': chunk})}\n\n"
            else:
                async for delta in llm_client.chat_stream(model, history, usage_sink=usage_sink):
                    full_reply += delta
                    yield f"data: {json.dumps({'delta': delta})}\n\n"

            # A real, sandboxed run of the reply's first python code block, not the model's own
            # guess at what it would print — appended (and streamed) the same way for every
            # branch above, so "does this actually work" is answered the same regardless of
            # whether tools, MAX mode, or plain generation produced the code.
            output_section = await maybe_run_code_and_format_output(full_reply)
            if output_section:
                full_reply += output_section
                yield f"data: {json.dumps({'delta': output_section})}\n\n"
        finally:
            if full_reply:
                assistant_message = Message(conversation_id=conversation.id, role="assistant", content=full_reply)
                db.add(assistant_message)
                db.commit()
                if generated_image_id is not None:
                    generated_image = db.get(Image, generated_image_id)
                    if generated_image is not None and generated_image.user_id == conversation.user_id:
                        generated_image.message_id = assistant_message.id
                        db.commit()
                if expert_pipeline_steps:
                    db.add_all(
                        [
                            ExpertPipelineStep(
                                message_id=assistant_message.id,
                                step_index=i,
                                step_type=s.step.step_type,
                                instruction=s.step.instruction,
                                model=s.model,
                                raw_output=s.raw_output,
                                verified_output=s.verified_output,
                            )
                            for i, s in enumerate(expert_pipeline_steps)
                        ]
                    )
                    db.commit()
                elif max_mode_results:
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
                elif agent_steps:
                    db.add_all(
                        [
                            AgentStep(
                                message_id=assistant_message.id,
                                step_index=i,
                                assistant_reply=s.assistant_reply,
                                tool_name=s.tool_name,
                                tool_result=s.tool_result,
                            )
                            for i, s in enumerate(agent_steps)
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
