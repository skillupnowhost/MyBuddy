import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.videos import get_owned_video
from app.core.deps import get_current_user, get_db
from app.db.models.image import Image
from app.db.models.user import User
from app.db.models.video_edit_job import VideoEditJob
from app.schemas.video_edit import VideoEditCreate, VideoEditRead
from app.services.video_edit_service import cancel_video_edit_job, launch_video_edit_job

router = APIRouter(prefix="/video-edit", tags=["video-edit"])


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> VideoEditJob:
    job = db.get(VideoEditJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video edit job not found")
    return job


@router.post("", response_model=VideoEditRead, status_code=status.HTTP_201_CREATED)
def create_video_edit_job(
    payload: VideoEditCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    source_video = get_owned_video(db, payload.source_video_id, user)

    mask_image = None
    if payload.mask_image_id is not None:
        mask_image = db.get(Image, payload.mask_image_id)
        if mask_image is None or mask_image.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mask image not found")

    background_image = None
    if payload.background_image_id is not None:
        background_image = db.get(Image, payload.background_image_id)
        if background_image is None or background_image.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Background image not found")

    job = VideoEditJob(
        user_id=user.id,
        operation=payload.operation,
        source_video_id=payload.source_video_id,
        background_color=payload.background_color,
        background_image_id=payload.background_image_id,
        mask_image_id=payload.mask_image_id,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        steps=payload.steps,
        color_preset=payload.color_preset,
        vfx_type=payload.vfx_type,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_video_edit_job(
            str(job.id),
            str(user.id),
            payload.operation,
            source_video.storage_path,
            payload.background_color,
            mask_image.storage_path if mask_image is not None else None,
            payload.prompt,
            payload.negative_prompt,
            payload.steps,
            background_image.storage_path if background_image is not None else None,
            payload.color_preset,
            payload.vfx_type,
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch video edit process: {exc}"
        db.commit()

    return job


@router.get("", response_model=list[VideoEditRead])
def list_video_edit_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(VideoEditJob).filter(VideoEditJob.user_id == user.id).order_by(VideoEditJob.created_at.desc()).all()


@router.get("/{job_id}", response_model=VideoEditRead)
def get_video_edit_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_job(db, job_id, user)


@router.post("/{job_id}/cancel", response_model=VideoEditRead)
def cancel_video_edit_job_endpoint(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _get_owned_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_video_edit_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
