import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.image import Image
from app.db.models.image_edit_job import ImageEditJob
from app.db.models.user import User
from app.schemas.image_edit import ImageEditCreate, ImageEditRead
from app.services.image_edit_service import cancel_image_edit_job, launch_image_edit_job

settings = get_settings()
router = APIRouter(prefix="/image-edit", tags=["image-edit"])


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> ImageEditJob:
    job = db.get(ImageEditJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image edit job not found")
    return job


def _get_owned_image(db: Session, image_id: uuid.UUID, user: User) -> Image:
    image = db.get(Image, image_id)
    if image is None or image.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image


@router.post("", response_model=ImageEditRead, status_code=status.HTTP_201_CREATED)
def create_image_edit_job(
    payload: ImageEditCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_owned_image(db, payload.source_image_id, user)

    params: dict = {}
    if payload.operation == "INPAINT":
        if payload.mask_image_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inpainting requires a mask_image_id.")
        _get_owned_image(db, payload.mask_image_id, user)
        if not payload.prompt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inpainting requires a prompt.")
    elif payload.operation == "OUTPAINT":
        if not payload.prompt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Outpainting requires a prompt.")
        padding = (payload.outpaint_top, payload.outpaint_bottom, payload.outpaint_left, payload.outpaint_right)
        if all(p <= 0 for p in padding):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Outpainting requires at least one positive outpaint_top/bottom/left/right value.",
            )
        if any(p > settings.image_edit_max_outpaint_padding for p in padding):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Outpaint padding must not exceed {settings.image_edit_max_outpaint_padding}px per side.",
            )
        params = {
            "outpaint_top": payload.outpaint_top,
            "outpaint_bottom": payload.outpaint_bottom,
            "outpaint_left": payload.outpaint_left,
            "outpaint_right": payload.outpaint_right,
        }

    if payload.operation in ("INPAINT", "OUTPAINT") and payload.steps > settings.image_edit_max_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"steps must not exceed {settings.image_edit_max_steps}.",
        )

    job = ImageEditJob(
        user_id=user.id,
        operation=payload.operation,
        source_image_id=payload.source_image_id,
        mask_image_id=payload.mask_image_id if payload.operation == "INPAINT" else None,
        prompt=payload.prompt if payload.operation != "REMOVE_BACKGROUND" else None,
        negative_prompt=payload.negative_prompt if payload.operation != "REMOVE_BACKGROUND" else None,
        steps=payload.steps if payload.operation != "REMOVE_BACKGROUND" else None,
        params=params,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_image_edit_job(
            str(job.id),
            str(user.id),
            payload.operation,
            str(payload.source_image_id),
            str(payload.mask_image_id) if payload.mask_image_id else None,
            job.prompt,
            job.negative_prompt,
            job.steps or settings.image_edit_default_steps,
            payload.outpaint_top,
            payload.outpaint_bottom,
            payload.outpaint_left,
            payload.outpaint_right,
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch image edit process: {exc}"
        db.commit()

    return job


@router.get("", response_model=list[ImageEditRead])
def list_image_edit_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(ImageEditJob).filter(ImageEditJob.user_id == user.id).order_by(ImageEditJob.created_at.desc()).all()


@router.get("/{job_id}", response_model=ImageEditRead)
def get_image_edit_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_job(db, job_id, user)


@router.post("/{job_id}/cancel", response_model=ImageEditRead)
def cancel_image_edit_job_endpoint(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    job = _get_owned_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_image_edit_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image_edit_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _get_owned_job(db, job_id, user)
    if job.status in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancel the job before deleting it.")
    db.delete(job)
    db.commit()
