import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.image import Image
from app.db.models.model_3d_generation_job import Model3DGenerationJob
from app.db.models.user import User
from app.schemas.model_3d_generation import Model3DGenerationCreate, Model3DGenerationRead
from app.services.model_3d_generation_service import cancel_model_3d_generation_job, launch_model_3d_generation_job

settings = get_settings()
router = APIRouter(prefix="/model3d-generation", tags=["model3d-generation"])


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> Model3DGenerationJob:
    job = db.get(Model3DGenerationJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="3D generation job not found")
    return job


@router.post("", response_model=Model3DGenerationRead, status_code=status.HTTP_201_CREATED)
def create_model_3d_generation_job(
    payload: Model3DGenerationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.steps > settings.cg3d_max_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"steps must not exceed {settings.cg3d_max_steps}."
        )
    if payload.steps < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="steps must be positive.")

    source_image_path = None
    if payload.source_image_id is not None:
        image = db.get(Image, payload.source_image_id)
        if image is None or image.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source image not found")
        source_image_path = image.storage_path

    job = Model3DGenerationJob(
        user_id=user.id,
        prompt=payload.prompt,
        source_image_id=payload.source_image_id,
        steps=payload.steps,
        guidance_scale=payload.guidance_scale,
        seed=payload.seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_model_3d_generation_job(
            str(job.id), str(user.id), payload.prompt, source_image_path, payload.steps, payload.guidance_scale, payload.seed
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch 3D generation process: {exc}"
        db.commit()

    return job


@router.get("", response_model=list[Model3DGenerationRead])
def list_model_3d_generation_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Model3DGenerationJob)
        .filter(Model3DGenerationJob.user_id == user.id)
        .order_by(Model3DGenerationJob.created_at.desc())
        .all()
    )


@router.get("/{job_id}", response_model=Model3DGenerationRead)
def get_model_3d_generation_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_job(db, job_id, user)


@router.post("/{job_id}/cancel", response_model=Model3DGenerationRead)
def cancel_model_3d_generation_job_endpoint(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    job = _get_owned_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_model_3d_generation_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
