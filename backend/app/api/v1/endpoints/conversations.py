import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.code_project import CodeProject
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationDetail, ConversationRead, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_owned_conversation(db: Session, conversation_id: uuid.UUID, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _validate_code_project(db: Session, code_project_id: uuid.UUID | None, user: User) -> None:
    """A conversation's code_project_id must belong to the same user — otherwise a
    conversation could retrieve another user's code via the code-RAG branch in
    chat_service. Same 404-not-403 isolation convention as every other owned resource."""
    if code_project_id is None:
        return
    project = db.get(CodeProject, code_project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code project not found")


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_code_project(db, payload.code_project_id, user)
    conversation = Conversation(
        user_id=user.id,
        title=payload.title or "New conversation",
        system_prompt=payload.system_prompt,
        model=payload.model,
        rag_enabled=payload.rag_enabled,
        tools_enabled=payload.tools_enabled,
        code_project_id=payload.code_project_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _get_owned_conversation(db, conversation_id, user)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    updates = payload.model_dump(exclude_unset=True)
    if "code_project_id" in updates:
        _validate_code_project(db, updates["code_project_id"], user)
    for field, value in updates.items():
        setattr(conversation, field, value)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()
