import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.vector_document import VectorDocument
from app.db.models.vector_object import VectorObject
from app.schemas.vector import (
    VectorDocumentCreate,
    VectorDocumentRead,
    VectorEditRequest,
    VectorObjectCreate,
    VectorObjectPatch,
    VectorObjectRead,
)
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.vector_service import (
    VectorGenerationError,
    AddObjectOp,
    SetPropOp,
    apply_operation,
    generate_edit_operation,
    generate_scene,
    render_svg,
)

settings = get_settings()
router = APIRouter(prefix="/vector", tags=["vector"])


def _get_owned_document(db: Session, document_id: uuid.UUID, user: User) -> VectorDocument:
    document = db.get(VectorDocument, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector document not found")
    return document


def _get_owned_object(db: Session, document: VectorDocument, object_id: uuid.UUID) -> VectorObject:
    obj = db.get(VectorObject, object_id)
    if obj is None or obj.document_id != document.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return obj


@router.post("/documents", response_model=VectorDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_vector_document(
    payload: VectorDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    purpose_defaults = settings.vector_purpose_defaults[payload.purpose]
    canvas_width = payload.canvas_width if payload.canvas_width is not None else purpose_defaults["canvas_width"]
    canvas_height = payload.canvas_height if payload.canvas_height is not None else purpose_defaults["canvas_height"]
    max_objects = min(purpose_defaults["max_objects"], settings.vector_max_objects_per_document)

    if not (1 <= canvas_width <= settings.vector_canvas_max_width) or not (
        1 <= canvas_height <= settings.vector_canvas_max_height
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"canvas dimensions must be between 1 and {settings.vector_canvas_max_width}x"
            f"{settings.vector_canvas_max_height}.",
        )

    try:
        object_creates = await generate_scene(
            llm_client, settings.ollama_model, payload.prompt, max_objects, settings.vector_max_retries, payload.purpose
        )
    except VectorGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    document = VectorDocument(
        user_id=user.id,
        title=payload.prompt[:255],
        purpose=payload.purpose,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    db.add(document)
    db.flush()

    for oc in object_creates:
        db.add(
            VectorObject(
                document_id=document.id,
                object_type=oc.props.object_type,
                z_index=oc.z_index,
                layer_name=oc.layer_name,
                props=oc.props.model_dump(),
            )
        )
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents", response_model=list[VectorDocumentRead])
def list_vector_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(VectorDocument)
        .filter(VectorDocument.user_id == user.id)
        .order_by(VectorDocument.created_at.desc())
        .all()
    )


@router.get("/documents/{document_id}", response_model=VectorDocumentRead)
def get_vector_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_document(db, document_id, user)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vector_document(
    document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = _get_owned_document(db, document_id, user)
    db.delete(document)
    db.commit()


@router.post("/documents/{document_id}/edit", response_model=VectorDocumentRead)
async def edit_vector_document(
    document_id: uuid.UUID,
    payload: VectorEditRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    document = _get_owned_document(db, document_id, user)
    objects = list(document.objects)

    try:
        op = await generate_edit_operation(
            llm_client, settings.ollama_model, objects, payload.instruction, settings.vector_max_retries
        )
    except VectorGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    try:
        apply_operation(db, document, op)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.refresh(document)
    return document


@router.post("/documents/{document_id}/objects", response_model=VectorObjectRead, status_code=status.HTTP_201_CREATED)
def add_vector_object(
    document_id: uuid.UUID,
    payload: VectorObjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_owned_document(db, document_id, user)
    if len(document.objects) >= settings.vector_max_objects_per_document:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A document can have at most {settings.vector_max_objects_per_document} objects.",
        )
    obj = apply_operation(db, document, AddObjectOp(object=payload))
    return obj


@router.patch("/documents/{document_id}/objects/{object_id}", response_model=VectorObjectRead)
def update_vector_object(
    document_id: uuid.UUID,
    object_id: uuid.UUID,
    payload: VectorObjectPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Applies {"prop": "<field name>", "value": <number or string>} through the exact same
    apply_operation() path the AI-edit endpoint uses."""
    document = _get_owned_document(db, document_id, user)
    _get_owned_object(db, document, object_id)

    try:
        obj = apply_operation(
            db, document, SetPropOp(object_id=object_id, prop=payload.prop, value=payload.value)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return obj


@router.delete("/documents/{document_id}/objects/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vector_object(
    document_id: uuid.UUID,
    object_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = _get_owned_document(db, document_id, user)
    obj = _get_owned_object(db, document, object_id)
    db.delete(obj)
    db.commit()


@router.get("/documents/{document_id}/export")
def export_vector_document(
    document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    document = _get_owned_document(db, document_id, user)
    svg = render_svg(document, list(document.objects))
    return Response(content=svg, media_type="image/svg+xml")
