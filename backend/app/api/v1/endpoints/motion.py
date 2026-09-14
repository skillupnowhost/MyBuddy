import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.animation import _get_owned_animation
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.animation_document import AnimationDocument
from app.db.models.motion_clip import MotionClip
from app.db.models.motion_project import MotionProject
from app.db.models.user import User
from app.db.models.vector_document import VectorDocument
from app.schemas.motion import (
    MotionClipCreate,
    MotionClipPatch,
    MotionClipRead,
    MotionProjectCreate,
    MotionProjectRead,
)
from app.services.motion_service import ClipRenderData, render_motion_svg

settings = get_settings()
router = APIRouter(prefix="/motion", tags=["motion"])


def _get_owned_project(db: Session, project_id: uuid.UUID, user: User) -> MotionProject:
    project = db.get(MotionProject, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motion project not found")
    return project


def _get_owned_clip(db: Session, project: MotionProject, clip_id: uuid.UUID) -> MotionClip:
    clip = db.get(MotionClip, clip_id)
    if clip is None or clip.motion_project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


@router.post("/projects", response_model=MotionProjectRead, status_code=status.HTTP_201_CREATED)
def create_motion_project(
    payload: MotionProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if not (1 <= payload.total_duration_ms <= settings.motion_max_total_duration_ms):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"total_duration_ms must be between 1 and {settings.motion_max_total_duration_ms}.",
        )
    if not (1 <= payload.canvas_width <= settings.vector_canvas_max_width) or not (
        1 <= payload.canvas_height <= settings.vector_canvas_max_height
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"canvas dimensions must be between 1 and {settings.vector_canvas_max_width}x"
            f"{settings.vector_canvas_max_height}.",
        )

    project = MotionProject(
        user_id=user.id,
        title=payload.title,
        canvas_width=payload.canvas_width,
        canvas_height=payload.canvas_height,
        total_duration_ms=payload.total_duration_ms,
        loop=payload.loop,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[MotionProjectRead])
def list_motion_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(MotionProject)
        .filter(MotionProject.user_id == user.id)
        .order_by(MotionProject.created_at.desc())
        .all()
    )


@router.get("/projects/{project_id}", response_model=MotionProjectRead)
def get_motion_project(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_project(db, project_id, user)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_motion_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    project = _get_owned_project(db, project_id, user)
    db.delete(project)
    db.commit()


@router.post("/projects/{project_id}/clips", response_model=MotionClipRead, status_code=status.HTTP_201_CREATED)
def add_clip(
    project_id: uuid.UUID,
    payload: MotionClipCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    if len(project.clips) >= settings.motion_max_clips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A motion project can have at most {settings.motion_max_clips} clips.",
        )

    animation = _get_owned_animation(db, payload.animation_document_id, user)
    if payload.start_offset_ms + animation.duration_ms > project.total_duration_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This clip (start offset + animation duration) does not fit within the "
            "project's total_duration_ms.",
        )

    clip = MotionClip(
        motion_project_id=project.id,
        animation_document_id=animation.id,
        start_offset_ms=payload.start_offset_ms,
        x_offset=payload.x_offset,
        y_offset=payload.y_offset,
        z_index=payload.z_index,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@router.patch("/projects/{project_id}/clips/{clip_id}", response_model=MotionClipRead)
def update_clip(
    project_id: uuid.UUID,
    clip_id: uuid.UUID,
    payload: MotionClipPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    clip = _get_owned_clip(db, project, clip_id)

    new_offset = payload.start_offset_ms if payload.start_offset_ms is not None else clip.start_offset_ms
    animation = db.get(AnimationDocument, clip.animation_document_id)
    if new_offset + animation.duration_ms > project.total_duration_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This clip (start offset + animation duration) does not fit within the "
            "project's total_duration_ms.",
        )

    if payload.start_offset_ms is not None:
        clip.start_offset_ms = payload.start_offset_ms
    if payload.x_offset is not None:
        clip.x_offset = payload.x_offset
    if payload.y_offset is not None:
        clip.y_offset = payload.y_offset
    if payload.z_index is not None:
        clip.z_index = payload.z_index

    db.commit()
    db.refresh(clip)
    return clip


@router.delete("/projects/{project_id}/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_clip(
    project_id: uuid.UUID,
    clip_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    clip = _get_owned_clip(db, project, clip_id)
    db.delete(clip)
    db.commit()


@router.get("/projects/{project_id}/export")
def export_motion_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    project = _get_owned_project(db, project_id, user)

    clip_data = []
    for clip in project.clips:
        animation = db.get(AnimationDocument, clip.animation_document_id)
        vector_document = db.get(VectorDocument, animation.vector_document_id)
        clip_data.append(
            ClipRenderData(
                clip=clip,
                vector_document=vector_document,
                objects=list(vector_document.objects),
                keyframes=list(animation.keyframes),
            )
        )

    svg = render_motion_svg(project, clip_data)
    return Response(content=svg, media_type="image/svg+xml")
