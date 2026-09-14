import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.character import Character
from app.db.models.image import Image
from app.db.models.user import User
from app.schemas.character import CharacterCreate, CharacterPatch, CharacterRead

router = APIRouter(prefix="/characters", tags=["characters"])


def get_owned_character(db: Session, character_id: uuid.UUID, user: User) -> Character:
    """Exported for other endpoints (storyboard) that need to validate a character_id
    belongs to the current user before using it as a consistency input."""
    character = db.get(Character, character_id)
    if character is None or character.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character


def _validate_reference_image(db: Session, image_id: uuid.UUID | None, user: User) -> None:
    if image_id is None:
        return
    image = db.get(Image, image_id)
    if image is None or image.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference image not found")


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _validate_reference_image(db, payload.reference_image_id, user)
    character = Character(user_id=user.id, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.get("", response_model=list[CharacterRead])
def list_characters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Character).filter(Character.user_id == user.id).order_by(Character.created_at.desc()).all()


@router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_owned_character(db, character_id, user)


@router.patch("/{character_id}", response_model=CharacterRead)
def update_character(
    character_id: uuid.UUID,
    payload: CharacterPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    character = get_owned_character(db, character_id, user)
    updates = payload.model_dump(exclude_unset=True)
    if "reference_image_id" in updates:
        _validate_reference_image(db, updates["reference_image_id"], user)
    for field, value in updates.items():
        setattr(character, field, value)
    db.commit()
    db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    character = get_owned_character(db, character_id, user)
    db.delete(character)
    db.commit()
