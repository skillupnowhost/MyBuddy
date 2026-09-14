import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.vector import _get_owned_document as _get_owned_vector_document
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.animation_document import AnimationDocument
from app.db.models.animation_keyframe import AnimationKeyframe
from app.db.models.user import User
from app.db.models.vector_document import VectorDocument
from app.db.models.vector_object import VectorObject
from app.schemas.animation import (
    AnimationDocumentCreate,
    AnimationDocumentRead,
    AnimationKeyframeCreate,
    AnimationKeyframePatch,
    AnimationKeyframeRead,
)
from app.services.animation_service import (
    _ANIMATABLE_PROPS_BY_TYPE,
    generate_keyframes,
    render_animation_svg,
)
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.vector_service import VectorGenerationError, validate_prop_value

settings = get_settings()
router = APIRouter(prefix="/animation", tags=["animation"])


def _get_owned_animation(db: Session, animation_id: uuid.UUID, user: User) -> AnimationDocument:
    animation = db.get(AnimationDocument, animation_id)
    if animation is None or animation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animation not found")
    return animation


def _get_owned_keyframe(db: Session, animation: AnimationDocument, keyframe_id: uuid.UUID) -> AnimationKeyframe:
    kf = db.get(AnimationKeyframe, keyframe_id)
    if kf is None or kf.animation_id != animation.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyframe not found")
    return kf


def _validate_keyframe_prop_value(object_id: uuid.UUID, prop: str, value, objects_by_id: dict[str, VectorObject]):
    obj = objects_by_id.get(str(object_id))
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found in this document.")
    if prop not in _ANIMATABLE_PROPS_BY_TYPE.get(obj.object_type, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{prop}' is not an animatable property for a {obj.object_type}.",
        )
    try:
        return validate_prop_value(obj.object_type, prop, value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/documents", response_model=AnimationDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_animation_document(
    payload: AnimationDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    vector_document = _get_owned_vector_document(db, payload.vector_document_id, user)
    objects = list(vector_document.objects)
    if not objects:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This document has no objects to animate.")

    duration_ms = payload.duration_ms if payload.duration_ms is not None else settings.animation_default_duration_ms
    frame_rate = payload.frame_rate if payload.frame_rate is not None else settings.animation_default_frame_rate
    if not (1 <= duration_ms <= settings.animation_max_duration_ms):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"duration_ms must be between 1 and {settings.animation_max_duration_ms}.",
        )

    try:
        keyframe_creates = await generate_keyframes(
            llm_client,
            settings.ollama_model,
            objects,
            payload.prompt,
            duration_ms,
            settings.animation_max_keyframes,
            settings.vector_max_retries,
        )
    except VectorGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    animation = AnimationDocument(
        user_id=user.id,
        vector_document_id=vector_document.id,
        title=payload.prompt[:255],
        frame_rate=frame_rate,
        duration_ms=duration_ms,
        loop=payload.loop,
    )
    db.add(animation)
    db.flush()

    for kc in keyframe_creates:
        db.add(
            AnimationKeyframe(
                animation_id=animation.id,
                object_id=kc.object_id,
                time_ms=kc.time_ms,
                prop=kc.prop,
                value=kc.value,
                easing=kc.easing,
            )
        )
    db.commit()
    db.refresh(animation)
    return animation


@router.get("/documents", response_model=list[AnimationDocumentRead])
def list_animation_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(AnimationDocument)
        .filter(AnimationDocument.user_id == user.id)
        .order_by(AnimationDocument.created_at.desc())
        .all()
    )


@router.get("/documents/{animation_id}", response_model=AnimationDocumentRead)
def get_animation_document(animation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_animation(db, animation_id, user)


@router.delete("/documents/{animation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animation_document(
    animation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    animation = _get_owned_animation(db, animation_id, user)
    db.delete(animation)
    db.commit()


@router.post(
    "/documents/{animation_id}/keyframes", response_model=AnimationKeyframeRead, status_code=status.HTTP_201_CREATED
)
def add_keyframe(
    animation_id: uuid.UUID,
    payload: AnimationKeyframeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    animation = _get_owned_animation(db, animation_id, user)
    if len(animation.keyframes) >= settings.animation_max_keyframes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An animation can have at most {settings.animation_max_keyframes} keyframes.",
        )
    vector_document = db.get(VectorDocument, animation.vector_document_id)
    objects_by_id = {str(o.id): o for o in vector_document.objects}
    value = _validate_keyframe_prop_value(payload.object_id, payload.prop, payload.value, objects_by_id)

    kf = AnimationKeyframe(
        animation_id=animation.id,
        object_id=payload.object_id,
        time_ms=payload.time_ms,
        prop=payload.prop,
        value=value,
        easing=payload.easing,
    )
    db.add(kf)
    db.commit()
    db.refresh(kf)
    return kf


@router.patch("/documents/{animation_id}/keyframes/{keyframe_id}", response_model=AnimationKeyframeRead)
def update_keyframe(
    animation_id: uuid.UUID,
    keyframe_id: uuid.UUID,
    payload: AnimationKeyframePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    animation = _get_owned_animation(db, animation_id, user)
    kf = _get_owned_keyframe(db, animation, keyframe_id)

    if payload.prop is not None or payload.value is not None:
        vector_document = db.get(VectorDocument, animation.vector_document_id)
        objects_by_id = {str(o.id): o for o in vector_document.objects}
        new_prop = payload.prop if payload.prop is not None else kf.prop
        new_value = payload.value if payload.value is not None else kf.value
        kf.value = _validate_keyframe_prop_value(kf.object_id, new_prop, new_value, objects_by_id)
        kf.prop = new_prop
    if payload.time_ms is not None:
        kf.time_ms = payload.time_ms
    if payload.easing is not None:
        kf.easing = payload.easing

    db.commit()
    db.refresh(kf)
    return kf


@router.delete("/documents/{animation_id}/keyframes/{keyframe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyframe(
    animation_id: uuid.UUID,
    keyframe_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    animation = _get_owned_animation(db, animation_id, user)
    kf = _get_owned_keyframe(db, animation, keyframe_id)
    db.delete(kf)
    db.commit()


@router.get("/documents/{animation_id}/export")
def export_animation_document(
    animation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    animation = _get_owned_animation(db, animation_id, user)
    vector_document = db.get(VectorDocument, animation.vector_document_id)
    svg = render_animation_svg(vector_document, list(vector_document.objects), animation, list(animation.keyframes))
    return Response(content=svg, media_type="image/svg+xml")
