import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.world_bible import WorldBible
from app.schemas.world_bible import WorldBibleCreate, WorldBiblePatch, WorldBibleRead

router = APIRouter(prefix="/world-bibles", tags=["world-bibles"])


def get_owned_world_bible(db: Session, world_bible_id: uuid.UUID, user: User) -> WorldBible:
    """Exported for other endpoints (storyboard) that need to validate a world_bible_id
    belongs to the current user before using it as a consistency input."""
    world_bible = db.get(WorldBible, world_bible_id)
    if world_bible is None or world_bible.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World bible not found")
    return world_bible


@router.post("", response_model=WorldBibleRead, status_code=status.HTTP_201_CREATED)
def create_world_bible(
    payload: WorldBibleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    world_bible = WorldBible(user_id=user.id, **payload.model_dump())
    db.add(world_bible)
    db.commit()
    db.refresh(world_bible)
    return world_bible


@router.get("", response_model=list[WorldBibleRead])
def list_world_bibles(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(WorldBible).filter(WorldBible.user_id == user.id).order_by(WorldBible.created_at.desc()).all()


@router.get("/{world_bible_id}", response_model=WorldBibleRead)
def get_world_bible(world_bible_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_owned_world_bible(db, world_bible_id, user)


@router.patch("/{world_bible_id}", response_model=WorldBibleRead)
def update_world_bible(
    world_bible_id: uuid.UUID,
    payload: WorldBiblePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    world_bible = get_owned_world_bible(db, world_bible_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(world_bible, field, value)
    db.commit()
    db.refresh(world_bible)
    return world_bible


@router.delete("/{world_bible_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_bible(
    world_bible_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    world_bible = get_owned_world_bible(db, world_bible_id, user)
    db.delete(world_bible)
    db.commit()
