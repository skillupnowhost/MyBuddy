import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.conversation import Conversation
from app.db.models.creative_project import CreativeProject
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceDetail, WorkspacePatch, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def get_owned_workspace(db: Session, workspace_id: uuid.UUID, user: User) -> Workspace:
    """Exported for other endpoints (conversations, creative) that need to validate a
    workspace_id belongs to the current user before assigning a resource to it."""
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Workspace).filter(Workspace.user_id == user.id).order_by(Workspace.updated_at.desc()).all()


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = Workspace(user_id=user.id, name=payload.name, description=payload.description)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = get_owned_workspace(db, workspace_id, user)
    workspace.conversations = (
        db.query(Conversation)
        .filter(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    workspace.creative_projects = (
        db.query(CreativeProject)
        .filter(CreativeProject.workspace_id == workspace_id)
        .order_by(CreativeProject.updated_at.desc())
        .all()
    )
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspacePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = get_owned_workspace(db, workspace_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Deleting a workspace never deletes its conversations/creative projects — their
    workspace_id is SET NULL at the DB level, they just become unassigned again."""
    workspace = get_owned_workspace(db, workspace_id, user)
    db.delete(workspace)
    db.commit()
