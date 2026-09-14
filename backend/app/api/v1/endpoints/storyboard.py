import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.storyboard import Storyboard
from app.db.models.storyboard_shot import StoryboardShot
from app.db.models.user import User
from app.schemas.storyboard import StoryboardDetail, StoryboardGenerateRequest, StoryboardRead
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.model_router import get_model_router
from app.services.storyboard_service import StoryboardGenerationError, generate_storyboard

settings = get_settings()
router = APIRouter(prefix="/storyboards", tags=["storyboards"])


def _get_owned_storyboard(db: Session, storyboard_id: uuid.UUID, user: User) -> Storyboard:
    storyboard = db.get(Storyboard, storyboard_id)
    if storyboard is None or storyboard.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard not found")
    return storyboard


@router.post("", response_model=StoryboardDetail, status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    payload: StoryboardGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    model = get_model_router().select(db, "TEXT").base_model
    try:
        shots = await generate_storyboard(
            llm_client, model, payload.script, settings.storyboard_max_shots, settings.storyboard_max_retries
        )
    except StoryboardGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    storyboard = Storyboard(user_id=user.id, title=payload.title or "Untitled storyboard", script=payload.script)
    db.add(storyboard)
    db.flush()  # assigns storyboard.id without committing yet, so shots can reference it

    db.add_all(
        [
            StoryboardShot(storyboard_id=storyboard.id, shot_index=i, **shot.model_dump())
            for i, shot in enumerate(shots)
        ]
    )
    db.commit()
    db.refresh(storyboard)
    return storyboard


@router.get("", response_model=list[StoryboardRead])
def list_storyboards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Storyboard).filter(Storyboard.user_id == user.id).order_by(Storyboard.created_at.desc()).all()


@router.get("/{storyboard_id}", response_model=StoryboardDetail)
def get_storyboard(storyboard_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_storyboard(db, storyboard_id, user)


@router.delete("/{storyboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storyboard(storyboard_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    storyboard = _get_owned_storyboard(db, storyboard_id, user)
    db.delete(storyboard)
    db.commit()
