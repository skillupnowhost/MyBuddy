import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.video import Video
from app.schemas.video_generation import VideoRead
from app.services.storage import delete_upload, save_video

settings = get_settings()
router = APIRouter(prefix="/videos", tags=["videos"])


def get_owned_video(db: Session, video_id: uuid.UUID, user: User) -> Video:
    """Exported for other endpoints (video_edit) that need to validate a source video
    belongs to the current user."""
    video = db.get(Video, video_id)
    if video is None or video.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.post("", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
async def upload_video(file: UploadFile, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """width/height/duration_seconds are left null — see Video's docstring for why the API
    process doesn't probe uploaded video files."""
    if file.content_type not in settings.allowed_video_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported video type: {file.content_type}"
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(content) > settings.max_video_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Video exceeds the {settings.max_video_size_bytes // (1024 * 1024)}MB upload limit.",
        )

    storage_path = save_video(str(user.id), file.content_type, content)
    video = Video(user_id=user.id, storage_path=storage_path, content_type=file.content_type, size_bytes=len(content))
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.get("/{video_id}")
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Served only through this authenticated endpoint — same reasoning as images.get_image:
    a plain <video src> can't carry a bearer token, so the frontend must fetch this as a
    blob (mirroring the existing AuthedImage component's pattern)."""
    video = get_owned_video(db, video_id, user)
    return FileResponse(video.storage_path, media_type=video.content_type)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    video = get_owned_video(db, video_id, user)
    delete_upload(video.storage_path)
    db.delete(video)
    db.commit()
