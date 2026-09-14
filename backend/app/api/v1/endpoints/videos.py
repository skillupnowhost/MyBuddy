import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.video import Video
from app.services.storage import delete_upload

router = APIRouter(prefix="/videos", tags=["videos"])


def _get_owned_video(db: Session, video_id: uuid.UUID, user: User) -> Video:
    video = db.get(Video, video_id)
    if video is None or video.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.get("/{video_id}")
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Served only through this authenticated endpoint — same reasoning as images.get_image:
    a plain <video src> can't carry a bearer token, so the frontend must fetch this as a
    blob (mirroring the existing AuthedImage component's pattern)."""
    video = _get_owned_video(db, video_id, user)
    return FileResponse(video.storage_path, media_type=video.content_type)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    video = _get_owned_video(db, video_id, user)
    delete_upload(video.storage_path)
    db.delete(video)
    db.commit()
