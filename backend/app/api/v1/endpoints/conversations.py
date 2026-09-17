import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.workspaces import get_owned_workspace
from app.core.deps import get_current_user, get_db
from app.db.models.agent_step import AgentStep
from app.db.models.code_project import CodeProject
from app.db.models.conversation import Conversation
from app.db.models.expert_pipeline_step import ExpertPipelineStep
from app.db.models.max_mode_candidate import MaxModeCandidate
from app.db.models.message import Message
from app.db.models.user import User
from app.schemas.agent import AgentStepRead
from app.schemas.arena import MaxModeCandidateRead
from app.schemas.conversation import ConversationCreate, ConversationDetail, ConversationRead, ConversationUpdate
from app.schemas.expert_pipeline import ExpertPipelineStepRead
from app.schemas.message import MessageFeedbackUpdate, MessageRead

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


def _validate_workspace(db: Session, workspace_id: uuid.UUID | None, user: User) -> None:
    if workspace_id is None:
        return
    get_owned_workspace(db, workspace_id, user)  # raises 404 if missing/not owned


def _validate_reply_mode_exclusivity(max_mode_enabled: bool, expert_pipeline_enabled: bool, agent_mode_enabled: bool) -> None:
    """MAX mode, the Expert Pipeline, and Agent mode are alternate reply strategies for the
    same turn (see chat_service.stream_assistant_reply) — enabling more than one would leave
    it ambiguous which actually runs, so reject the combination outright rather than picking
    one silently."""
    if sum([max_mode_enabled, expert_pipeline_enabled, agent_mode_enabled]) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="only one of max_mode_enabled, expert_pipeline_enabled, agent_mode_enabled may be true",
        )


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
    _validate_workspace(db, payload.workspace_id, user)
    _validate_reply_mode_exclusivity(payload.max_mode_enabled, payload.expert_pipeline_enabled, payload.agent_mode_enabled)
    conversation = Conversation(
        user_id=user.id,
        title=payload.title or "New conversation",
        system_prompt=payload.system_prompt,
        model=payload.model,
        rag_enabled=payload.rag_enabled,
        tools_enabled=payload.tools_enabled,
        max_mode_enabled=payload.max_mode_enabled,
        expert_pipeline_enabled=payload.expert_pipeline_enabled,
        agent_mode_enabled=payload.agent_mode_enabled,
        code_project_id=payload.code_project_id,
        workspace_id=payload.workspace_id,
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
    if "workspace_id" in updates:
        _validate_workspace(db, updates["workspace_id"], user)
    resulting_max_mode = updates.get("max_mode_enabled", conversation.max_mode_enabled)
    resulting_expert_pipeline = updates.get("expert_pipeline_enabled", conversation.expert_pipeline_enabled)
    resulting_agent_mode = updates.get("agent_mode_enabled", conversation.agent_mode_enabled)
    _validate_reply_mode_exclusivity(resulting_max_mode, resulting_expert_pipeline, resulting_agent_mode)
    for field, value in updates.items():
        setattr(conversation, field, value)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages/{message_id}", response_model=MessageRead)
def get_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


@router.get("/{conversation_id}/messages/{message_id}/max-candidates", response_model=list[MaxModeCandidateRead])
def get_max_mode_candidates_for_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transparency view for a MAX-mode turn: every candidate model's raw answer plus the
    judge's synthesis (see chat_service._max_mode_reply / MaxModeCandidate). Empty list for a
    normal (non-MAX-mode) message, not an error."""
    _get_owned_conversation(db, conversation_id, user)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return (
        db.query(MaxModeCandidate)
        .filter(MaxModeCandidate.message_id == message_id)
        .order_by(MaxModeCandidate.is_judge.asc(), MaxModeCandidate.created_at.asc())
        .all()
    )


@router.get(
    "/{conversation_id}/messages/{message_id}/expert-pipeline-steps",
    response_model=list[ExpertPipelineStepRead],
)
def get_expert_pipeline_steps_for_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transparency view for an Expert-Pipeline turn: every subtask's instruction, assigned
    model, raw output, and verified output (see expert_pipeline_service.run_expert_pipeline /
    ExpertPipelineStep). Empty list for a normal (non-pipeline) message, not an error."""
    _get_owned_conversation(db, conversation_id, user)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return (
        db.query(ExpertPipelineStep)
        .filter(ExpertPipelineStep.message_id == message_id)
        .order_by(ExpertPipelineStep.step_index.asc())
        .all()
    )


@router.get("/{conversation_id}/messages/{message_id}/agent-steps", response_model=list[AgentStepRead])
def get_agent_steps_for_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transparency view for an Agent-mode turn: every tool call the model made before its
    final answer (see agent_service.run_agent_loop / AgentStep). Empty list for a normal
    (non-agent, or agent-with-no-tool-calls) message, not an error."""
    _get_owned_conversation(db, conversation_id, user)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return (
        db.query(AgentStep)
        .filter(AgentStep.message_id == message_id)
        .order_by(AgentStep.step_index.asc())
        .all()
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()


@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageRead)
def update_message_feedback(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageFeedbackUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, user)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    message.feedback = payload.feedback
    db.commit()
    db.refresh(message)
    return message


@router.delete("/{conversation_id}/messages/{message_id}/onward", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_onward(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Deletes the given message and every message after it in the same conversation
    (ordered by created_at) — what "edit and resend" needs: discard the old turn (and
    whatever the assistant said in reply) before the edited content is sent as a new
    message, rather than leaving a stale exchange sitting in the middle of the history."""
    conversation = _get_owned_conversation(db, conversation_id, user)
    ordered = (
        db.query(Message.id)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    ordered_ids = [row[0] for row in ordered]
    try:
        target_index = ordered_ids.index(message_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found") from None

    # Deletes by id, not by a created_at cutoff — comparing timestamps for ">= this one"
    # is exactly the kind of thing that quietly behaves differently across database
    # backends (string vs. native datetime comparison), where deleting by an explicit id
    # list, computed once in Python from the same ordering the API returns, does not.
    ids_to_delete = ordered_ids[target_index:]
    db.query(Message).filter(Message.id.in_(ids_to_delete)).delete(synchronize_session=False)
    db.commit()
