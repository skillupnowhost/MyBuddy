import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.camera_plan import CameraPlan
from app.db.models.storyboard import Storyboard
from app.db.models.storyboard_shot import StoryboardShot
from app.db.models.user import User
from app.schemas.camera_plan import CameraPlanCreate, CameraPlanPatch, CameraPlanRead

router = APIRouter(prefix="/camera-plans", tags=["camera-plans"])


def _get_owned_camera_plan(db: Session, camera_plan_id: uuid.UUID, user: User) -> CameraPlan:
    plan = db.get(CameraPlan, camera_plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera plan not found")
    return plan


def _validate_storyboard_shot(db: Session, storyboard_shot_id: uuid.UUID | None, user: User) -> None:
    """A camera plan's shot must belong to a storyboard the caller owns — StoryboardShot has
    no user_id of its own, so this joins through its parent Storyboard, same reasoning as
    conversations._validate_code_project checking a nested resource's real owner."""
    if storyboard_shot_id is None:
        return
    shot = db.get(StoryboardShot, storyboard_shot_id)
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard shot not found")
    storyboard = db.get(Storyboard, shot.storyboard_id)
    if storyboard is None or storyboard.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard shot not found")


@router.post("", response_model=CameraPlanRead, status_code=status.HTTP_201_CREATED)
def create_camera_plan(
    payload: CameraPlanCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _validate_storyboard_shot(db, payload.storyboard_shot_id, user)
    plan = CameraPlan(user_id=user.id, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("", response_model=list[CameraPlanRead])
def list_camera_plans(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(CameraPlan).filter(CameraPlan.user_id == user.id).order_by(CameraPlan.created_at.desc()).all()


@router.get("/{camera_plan_id}", response_model=CameraPlanRead)
def get_camera_plan(camera_plan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_camera_plan(db, camera_plan_id, user)


@router.patch("/{camera_plan_id}", response_model=CameraPlanRead)
def update_camera_plan(
    camera_plan_id: uuid.UUID,
    payload: CameraPlanPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = _get_owned_camera_plan(db, camera_plan_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{camera_plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera_plan(
    camera_plan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    plan = _get_owned_camera_plan(db, camera_plan_id, user)
    db.delete(plan)
    db.commit()
