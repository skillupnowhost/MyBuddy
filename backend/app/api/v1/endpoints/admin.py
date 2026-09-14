import uuid

import psutil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin, get_db
from app.db.models.conversation import Conversation
from app.db.models.document import Document
from app.db.models.memory import Memory
from app.db.models.message import Message
from app.db.models.model_benchmark_result import ModelBenchmarkResult
from app.db.models.model_registry import RegisteredModel
from app.db.models.training_job import TrainingJob
from app.db.models.user import User
from app.schemas.admin import AdminStats, AdminUserRead, RoleUpdate, SystemHealth
from app.schemas.training import BenchmarkRunResult, ModelBenchmarkResultRead, RegisteredModelRead
from app.services.benchmark_service import run_benchmark
from app.services.llm_client import get_llm_client
from app.services.model_registry_service import discover_local_models

router = APIRouter(prefix="/admin", tags=["admin"])

_VALID_ROLES = {"USER", "ADMIN"}


@router.get("/users", response_model=list[AdminUserRead])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=AdminUserRead)
def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if payload.role not in _VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"role must be one of {_VALID_ROLES}")
    if user_id == admin.id and payload.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote your own account")

    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target


@router.get("/stats", response_model=AdminStats)
def get_stats(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    return AdminStats(
        total_users=db.query(User).count(),
        total_conversations=db.query(Conversation).count(),
        total_messages=db.query(Message).count(),
        total_documents=db.query(Document).count(),
        total_memories=db.query(Memory).count(),
        total_training_jobs=db.query(TrainingJob).count(),
    )


@router.post("/models/discover", response_model=list[RegisteredModelRead])
async def discover_models(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Scans what's actually installed in the local Ollama server and registers anything new
    as EXPERIMENTAL (see model_registry_service.discover_local_models). Admin-only, and
    discovery alone never makes a model selectable by the router — it still needs an explicit
    promotion to PRODUCTION via PATCH /models/registry/{id}/promote."""
    return await discover_local_models(db, get_llm_client())


def _get_registered_model(db: Session, model_id: uuid.UUID) -> RegisteredModel:
    model = db.get(RegisteredModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


@router.post("/models/{model_id}/benchmark", response_model=BenchmarkRunResult)
async def benchmark_model(
    model_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    """Runs the fixed benchmark suite for this model's capability (see benchmark_service.py)
    and writes the average score to eval_score — what FrontierModelRouter actually ranks
    candidates by. Capabilities without a defined suite yet (VISION, EMBEDDING) return an
    empty result list rather than a fabricated score."""
    model = _get_registered_model(db, model_id)
    results = await run_benchmark(db, get_llm_client(), model)
    return BenchmarkRunResult(results=results, eval_score=model.eval_score)


@router.get("/models/{model_id}/benchmark", response_model=list[ModelBenchmarkResultRead])
def list_benchmark_results(
    model_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    _get_registered_model(db, model_id)
    return (
        db.query(ModelBenchmarkResult)
        .filter(ModelBenchmarkResult.model_id == model_id)
        .order_by(ModelBenchmarkResult.created_at.desc())
        .all()
    )


@router.get("/health", response_model=SystemHealth)
async def get_system_health(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    database_ok = False
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:  # noqa: BLE001
        pass

    llm_ok = await get_llm_client().health()

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemHealth(
        cpu_percent=psutil.cpu_percent(interval=0.2),
        ram_used_gb=round((ram.total - ram.available) / (1024**3), 2),
        ram_total_gb=round(ram.total / (1024**3), 2),
        ram_percent=ram.percent,
        disk_used_gb=round(disk.used / (1024**3), 2),
        disk_total_gb=round(disk.total / (1024**3), 2),
        disk_percent=disk.percent,
        database_ok=database_ok,
        llm_ok=llm_ok,
    )
