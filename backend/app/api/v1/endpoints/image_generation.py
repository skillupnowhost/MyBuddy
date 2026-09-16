import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.image_generation_job import ImageGenerationJob
from app.db.models.user import User
from app.schemas.image_generation import ImageGenerationCreate, ImageGenerationRead
from app.services.image_generation_service import cancel_image_generation_job, launch_image_generation_job

settings = get_settings()
router = APIRouter(prefix="/image-generation", tags=["image-generation"])


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> ImageGenerationJob:
    job = db.get(ImageGenerationJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image generation job not found")
    return job


@router.post("", response_model=ImageGenerationRead, status_code=status.HTTP_201_CREATED)
def create_image_generation_job(
    payload: ImageGenerationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.width > settings.image_gen_max_width or payload.height > settings.image_gen_max_height:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"width/height must not exceed {settings.image_gen_max_width}x{settings.image_gen_max_height}.",
        )
    if payload.steps > settings.image_gen_max_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"steps must not exceed {settings.image_gen_max_steps}.",
        )
    if payload.width < 1 or payload.height < 1 or payload.steps < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="width/height/steps must be positive.")

    job = ImageGenerationJob(
        user_id=user.id,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        width=payload.width,
        height=payload.height,
        steps=payload.steps,
        seed=payload.seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_image_generation_job(
            str(job.id),
            str(user.id),
            payload.prompt,
            payload.negative_prompt,
            payload.width,
            payload.height,
            payload.steps,
            payload.seed,
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch image generation process: {exc}"
        db.commit()

    return job


@router.get("", response_model=list[ImageGenerationRead])
def list_image_generation_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ImageGenerationJob)
        .filter(ImageGenerationJob.user_id == user.id)
        .order_by(ImageGenerationJob.created_at.desc())
        .all()
    )


@router.get("/{job_id}", response_model=ImageGenerationRead)
def get_image_generation_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_job(db, job_id, user)


@router.post("/{job_id}/cancel", response_model=ImageGenerationRead)
def cancel_image_generation_job_endpoint(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    job = _get_owned_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_image_generation_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image_generation_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _get_owned_job(db, job_id, user)
    if job.status in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancel the job before deleting it.")
    db.delete(job)
    db.commit()
