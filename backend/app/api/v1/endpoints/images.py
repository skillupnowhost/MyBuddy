import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.image import Image
from app.db.models.user import User
from app.schemas.image import ImageRead
from app.services.storage import delete_upload, save_image

settings = get_settings()
router = APIRouter(prefix="/images", tags=["images"])


def _get_owned_image(db: Session, image_id: uuid.UUID, user: User) -> Image:
    image = db.get(Image, image_id)
    if image is None or image.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


@router.post("", response_model=ImageRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.content_type not in settings.allowed_image_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {file.content_type}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(content) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {settings.max_image_size_bytes // (1024 * 1024)}MB upload limit.",
        )

    storage_path = save_image(str(user.id), file.content_type, content)
    image = Image(
        user_id=user.id,
        storage_path=storage_path,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.get("/{image_id}")
def get_image(image_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    image = _get_owned_image(db, image_id, user)
    return FileResponse(image.storage_path, media_type=image.content_type)


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    image = _get_owned_image(db, image_id, user)
    if image.message_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an image that has already been sent in a message.",
        )
    delete_upload(image.storage_path)
    db.delete(image)
    db.commit()
