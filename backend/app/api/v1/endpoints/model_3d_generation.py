import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.image import Image
from app.db.models.model_3d_generation_job import Model3DGenerationJob
from app.db.models.user import User
from app.schemas.model_3d_generation import (
    Model3DGenerationCreate,
    Model3DGenerationRead,
    SceneGenerationRequest,
    SceneObjectRead,
)
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.model_3d_generation_service import cancel_model_3d_generation_job, launch_model_3d_generation_job
from app.services.model_router import get_model_router
from app.services.scene_decomposition_service import SceneDecompositionError, decompose_scene

settings = get_settings()
router = APIRouter(prefix="/model3d-generation", tags=["model3d-generation"])


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> Model3DGenerationJob:
    job = db.get(Model3DGenerationJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="3D generation job not found")
    return job


def _create_and_launch_job(db: Session, user_id: uuid.UUID, prompt: str) -> Model3DGenerationJob:
    """Shared by create_model_3d_generation_job (one explicit prompt) and generate_scene
    (one call per decomposed scene object) — same steps/guidance-scale defaults, no
    source_image_id (scene decomposition is text-only)."""
    job = Model3DGenerationJob(
        user_id=user_id,
        prompt=prompt,
        steps=settings.cg3d_default_steps,
        guidance_scale=settings.cg3d_default_guidance_scale,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_model_3d_generation_job(
            str(job.id), str(user_id), prompt, None, settings.cg3d_default_steps, settings.cg3d_default_guidance_scale, None
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch 3D generation process: {exc}"
        db.commit()

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


@router.post("/scenes", response_model=list[SceneObjectRead], status_code=status.HTTP_201_CREATED)
async def generate_scene(
    payload: SceneGenerationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    """AI 3D Scene Generator (spec §13), honestly scoped — see
    scene_decomposition_service.py's docstring: this decomposes a scene description into
    individual object prompts and launches one MyBuddy CG text-to-3D job per object. It does
    NOT place/scale/arrange the resulting meshes into one coherent scene file — Shap-E
    generates each mesh independently with no shared spatial context, and no real
    scene-composition engine exists in this project. The caller assembles the meshes
    afterward in a 3D tool."""
    model = get_model_router().select(db, "TEXT").base_model
    try:
        scene_objects = await decompose_scene(
            llm_client, model, payload.description, settings.cg3d_scene_max_objects, settings.cg3d_scene_max_retries
        )
    except SceneDecompositionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return [
        SceneObjectRead(label=obj.label, generation_job=_create_and_launch_job(db, user.id, obj.prompt))
        for obj in scene_objects
    ]


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
