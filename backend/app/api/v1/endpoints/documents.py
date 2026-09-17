import uuid
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, get_session_factory
from app.db.models.document import Document
from app.db.models.user import User
from app.schemas.document import DocumentRead
from app.services.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.services.rag_service import ingest_document
from app.services.storage import delete_upload, save_upload
from app.services.vector_store import VectorStoreProvider, get_vector_store

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["documents"])


def _get_owned_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


async def _run_ingestion(
    document_id: uuid.UUID,
    session_factory: Callable[[], Session],
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStoreProvider,
) -> None:
    db = session_factory()
    try:
        document = db.get(Document, document_id)
        if document is not None:
            await ingest_document(document, db, embedding_provider, vector_store)
    finally:
        db.close()


@router.get("", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_document(db, document_id, user)


@router.post("/{document_id}/retry", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def retry_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
):
    document = _get_owned_document(db, document_id, user)
    if document.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed documents can be retried.",
        )

    document.chunks.clear()
    document.status = "UPLOADING"
    document.error_message = None
    db.commit()
    db.refresh(document)
    background_tasks.add_task(_run_ingestion, document.id, session_factory, embedding_provider, vector_store)
    return document


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
):
    if file.content_type not in settings.allowed_upload_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_bytes // (1024 * 1024)}MB upload limit.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    storage_path = save_upload(str(user.id), file.content_type, content)

    document = Document(
        user_id=user.id,
        filename=file.filename or "untitled",
        content_type=file.content_type,
        size_bytes=len(content),
        storage_path=storage_path,
        status="UPLOADING",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(_run_ingestion, document.id, session_factory, embedding_provider, vector_store)

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
):
    document = _get_owned_document(db, document_id, user)
    chunk_ids = [str(c.id) for c in document.chunks]
    vector_store.delete(db, chunk_ids)
    delete_upload(document.storage_path)
    db.delete(document)
    db.commit()
