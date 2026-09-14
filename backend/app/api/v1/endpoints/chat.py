import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.endpoints.conversations import _get_owned_conversation
from app.core.deps import get_current_user, get_db, get_session_factory
from app.db.models.image import Image
from app.db.models.user import User
from app.schemas.message import MessageCreate, MessageRead
from app.services.chat_service import stream_assistant_reply
from app.services.code_vector_store import CodeVectorStoreProvider, get_code_vector_store
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.vector_store import VectorStoreProvider, get_vector_store

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    return conversation.messages


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
    code_vector_store: CodeVectorStoreProvider = Depends(get_code_vector_store),
):
    conversation = _get_owned_conversation(db, conversation_id, user)

    for image_id in payload.image_ids:
        image = db.get(Image, image_id)
        if image is None or image.user_id != user.id or image.message_id is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    generator = stream_assistant_reply(
        conversation.id,
        payload.content,
        llm_client,
        session_factory,
        embedding_provider,
        vector_store,
        code_vector_store,
        payload.image_ids,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
