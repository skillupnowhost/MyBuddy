import os
import shutil
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_admin, get_current_user, get_db, get_session_factory
from app.db.models.code_execution_job import CodeExecutionJob
from app.db.models.code_file import CodeFile
from app.db.models.code_project import CodeProject
from app.db.models.user import User
from app.schemas.code import CodeExecutionCreate, CodeExecutionRead, CodeFileContent, CodeFileRead, CodeProjectRead
from app.services.code_extraction import ZipValidationError, extract_code_zip
from app.services.code_rag_service import ingest_code_project
from app.services.code_vector_store import CodeVectorStoreProvider, get_code_vector_store
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.services.sandbox_provider import SandboxProvider
from app.services.subprocess_sandbox import get_sandbox_provider

settings = get_settings()
router = APIRouter(prefix="/code", tags=["code"])


def _get_owned_project(db: Session, project_id: uuid.UUID, user: User) -> CodeProject:
    project = db.get(CodeProject, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code project not found")
    return project


def _get_owned_file(db: Session, project_id: uuid.UUID, file_id: uuid.UUID, user: User) -> CodeFile:
    project = _get_owned_project(db, project_id, user)
    file = db.get(CodeFile, file_id)
    if file is None or file.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file


def _get_owned_execution(db: Session, job_id: uuid.UUID, user: User) -> CodeExecutionJob:
    job = db.get(CodeExecutionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution job not found")
    return job


async def _run_code_ingestion(
    project_id: uuid.UUID,
    extracted_files,
    session_factory: Callable[[], Session],
    embedding_provider: EmbeddingProvider,
    code_vector_store: CodeVectorStoreProvider,
) -> None:
    db = session_factory()
    try:
        project = db.get(CodeProject, project_id)
        if project is not None:
            await ingest_code_project(project, extracted_files, db, embedding_provider, code_vector_store)
    finally:
        db.close()


async def _run_sandbox_job(
    job_id: uuid.UUID,
    session_factory: Callable[[], Session],
    sandbox_provider: SandboxProvider,
) -> None:
    db = session_factory()
    try:
        job = db.get(CodeExecutionJob, job_id)
        if job is None:
            return
        try:
            job.status = "RUNNING"
            db.commit()

            result = await sandbox_provider.run(job.language, job.source)

            job.stdout = result.stdout
            job.stderr = result.stderr
            job.exit_code = result.exit_code
            job.stdout_truncated = result.stdout_truncated
            job.stderr_truncated = result.stderr_truncated
            job.duration_ms = result.duration_ms
            job.status = "TIMEOUT" if result.timed_out else ("COMPLETED" if result.exit_code == 0 else "FAILED")
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - a sandbox crash must surface as job status, not crash the task
            job.status = "FAILED"
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@router.post("/projects", response_model=CodeProjectRead, status_code=status.HTTP_201_CREATED)
async def upload_project(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    code_vector_store: CodeVectorStoreProvider = Depends(get_code_vector_store),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Code projects must be uploaded as a .zip archive.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(content) > settings.code_max_zip_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Zip exceeds the {settings.code_max_zip_size_bytes // (1024 * 1024)}MB upload limit.",
        )

    project_id = uuid.uuid4()
    dest_dir = os.path.join(settings.storage_dir, "code_projects", str(user.id), str(project_id))

    tmp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        tmp_zip.write(content)
        tmp_zip.close()

        try:
            extracted = extract_code_zip(tmp_zip.name, dest_dir)
        except ZipValidationError as exc:
            shutil.rmtree(dest_dir, ignore_errors=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        os.unlink(tmp_zip.name)

    if not extracted:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported source files were found in this zip.",
        )

    name = (file.filename or "untitled.zip").rsplit(".zip", 1)[0] or "untitled"
    project = CodeProject(
        id=project_id,
        user_id=user.id,
        name=name,
        storage_dir=dest_dir,
        status="EXTRACTING",
        file_count=len(extracted),
        total_size_bytes=sum(ef.size_bytes for ef in extracted),
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    background_tasks.add_task(
        _run_code_ingestion, project.id, extracted, session_factory, embedding_provider, code_vector_store
    )

    return project


@router.get("/projects", response_model=list[CodeProjectRead])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(CodeProject).filter(CodeProject.user_id == user.id).order_by(CodeProject.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=CodeProjectRead)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_project(db, project_id, user)


@router.get("/projects/{project_id}/tree", response_model=list[CodeFileRead])
def get_project_tree(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = _get_owned_project(db, project_id, user)
    return (
        db.query(CodeFile)
        .filter(CodeFile.project_id == project.id)
        .order_by(CodeFile.relative_path)
        .all()
    )


@router.get("/projects/{project_id}/files/{file_id}", response_model=CodeFileContent)
def get_file_content(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = _get_owned_file(db, project_id, file_id, user)
    try:
        with open(file.storage_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found on disk") from exc
    return CodeFileContent(
        id=file.id,
        relative_path=file.relative_path,
        language=file.language,
        size_bytes=file.size_bytes,
        content=content,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    code_vector_store: CodeVectorStoreProvider = Depends(get_code_vector_store),
):
    project = _get_owned_project(db, project_id, user)
    chunk_ids = [str(c.id) for f in project.files for c in f.chunks]
    code_vector_store.delete(db, chunk_ids)
    shutil.rmtree(project.storage_dir, ignore_errors=True)
    db.delete(project)
    db.commit()


# --- Sandbox (ADMIN-gated — see SubprocessSandboxProvider for why) ---


@router.post("/execute", response_model=CodeExecutionRead, status_code=status.HTTP_201_CREATED)
def submit_execution(
    payload: CodeExecutionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    sandbox_provider: SandboxProvider = Depends(get_sandbox_provider),
):
    if not settings.sandbox_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Code execution is disabled.")
    if payload.language not in settings.sandbox_allowed_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported language: {payload.language}"
        )

    job = CodeExecutionJob(user_id=admin.id, language=payload.language, source=payload.source, status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_sandbox_job, job.id, session_factory, sandbox_provider)

    return job


@router.get("/execute", response_model=list[CodeExecutionRead])
def list_executions(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return (
        db.query(CodeExecutionJob)
        .filter(CodeExecutionJob.user_id == admin.id)
        .order_by(CodeExecutionJob.created_at.desc())
        .all()
    )


@router.get("/execute/{job_id}", response_model=CodeExecutionRead)
def get_execution(job_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return _get_owned_execution(db, job_id, admin)
