import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.core.deps import get_current_admin, get_db
from app.db.models.dataset import Dataset
from app.db.models.model_registry import RegisteredModel
from app.db.models.training_job import TrainingJob
from app.db.models.user import User
from app.schemas.training import (
    DatasetRead,
    ModelPromotion,
    RegisteredModelRead,
    TrainingJobCreate,
    TrainingJobRead,
)
from app.services.dataset_service import apply_validation_result
from app.services.storage import delete_upload, save_dataset
from app.services.training_service import cancel_training_job, launch_training_job

router = APIRouter(tags=["fine-tuning"])


def _get_owned_dataset(db: Session, dataset_id: uuid.UUID, user: User) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


def _get_owned_job(db: Session, job_id: uuid.UUID, user: User) -> TrainingJob:
    job = db.get(TrainingJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training job not found")
    return job


@router.post("/datasets", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    if not (file.filename or "").endswith((".jsonl", ".json")):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dataset must be a .jsonl file (one JSON example per line).",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    storage_path = save_dataset(str(user.id), content)
    dataset = Dataset(user_id=user.id, filename=file.filename, storage_path=storage_path)
    apply_validation_result(dataset)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[DatasetRead])
def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    return db.query(Dataset).filter(Dataset.user_id == user.id).order_by(Dataset.created_at.desc()).all()


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    dataset = _get_owned_dataset(db, dataset_id, user)
    delete_upload(dataset.storage_path)
    db.delete(dataset)
    db.commit()


@router.post("/training-jobs", response_model=TrainingJobRead, status_code=status.HTTP_201_CREATED)
def create_training_job(
    payload: TrainingJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
):
    dataset = _get_owned_dataset(db, payload.dataset_id, user)
    if dataset.status != "VALIDATED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset must be VALIDATED before training (currently {dataset.status}).",
        )

    config = {
        "epochs": payload.epochs,
        "learning_rate": payload.learning_rate,
        "lora_r": payload.lora_r,
        "capability": payload.capability,
    }
    job = TrainingJob(user_id=user.id, dataset_id=dataset.id, base_model=payload.base_model, config=config)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_training_job(
            str(job.id), dataset.storage_path, payload.base_model, f"./output/{job.id}", payload.capability
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch training process: {exc}"
        db.commit()

    return job


@router.post("/training-jobs/{job_id}/cancel", response_model=TrainingJobRead)
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    job = _get_owned_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_training_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.get("/training-jobs", response_model=list[TrainingJobRead])
def list_training_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    return db.query(TrainingJob).filter(TrainingJob.user_id == user.id).order_by(TrainingJob.created_at.desc()).all()


@router.get("/training-jobs/{job_id}", response_model=TrainingJobRead)
def get_training_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    return _get_owned_job(db, job_id, user)


@router.get("/models/registry", response_model=list[RegisteredModelRead])
def list_registered_models(db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    return db.query(RegisteredModel).order_by(RegisteredModel.created_at.desc()).all()


@router.patch("/models/registry/{model_id}/promote", response_model=RegisteredModelRead)
def promote_model(
    model_id: uuid.UUID,
    payload: ModelPromotion,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Admin-only: moves a model along the promotion lifecycle (EXPERIMENTAL -> CANARY ->
    STAGING -> PRODUCTION, or -> ARCHIVED/REJECTED). Promoting a new model to PRODUCTION
    demotes whichever model currently holds that slot for the same base_model to ARCHIVED —
    never deleted, so a rollback is always just another promotion call away."""
    model = db.get(RegisteredModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if payload.status == "PRODUCTION":
        current_production = (
            db.query(RegisteredModel)
            .filter(RegisteredModel.base_model == model.base_model, RegisteredModel.status == "PRODUCTION")
            .filter(RegisteredModel.id != model.id)
            .all()
        )
        for other in current_production:
            other.status = "ARCHIVED"
        model.promoted_at = datetime.now(timezone.utc)

    model.status = payload.status
    db.commit()
    db.refresh(model)
    return model
