import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.videos import get_owned_video
from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.video_timeline import VideoTimeline
from app.db.models.video_timeline_clip import VideoTimelineClip
from app.db.models.video_timeline_export_job import VideoTimelineExportJob
from app.schemas.video_timeline import (
    VideoTimelineClipCreate,
    VideoTimelineClipRead,
    VideoTimelineCreate,
    VideoTimelineDetail,
    VideoTimelineExportRead,
    VideoTimelineRead,
)
from app.services.video_timeline_export_service import cancel_timeline_export_job, launch_timeline_export_job

router = APIRouter(prefix="/video-timelines", tags=["video-timelines"])


def _get_owned_timeline(db: Session, timeline_id: uuid.UUID, user: User) -> VideoTimeline:
    timeline = db.get(VideoTimeline, timeline_id)
    if timeline is None or timeline.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video timeline not found")
    return timeline


def _get_owned_clip(db: Session, timeline_id: uuid.UUID, clip_id: uuid.UUID, user: User) -> VideoTimelineClip:
    _get_owned_timeline(db, timeline_id, user)
    clip = db.get(VideoTimelineClip, clip_id)
    if clip is None or clip.timeline_id != timeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline clip not found")
    return clip


def _get_owned_export_job(db: Session, job_id: uuid.UUID, user: User) -> VideoTimelineExportJob:
    job = db.get(VideoTimelineExportJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline export job not found")
    return job


@router.post("", response_model=VideoTimelineRead, status_code=status.HTTP_201_CREATED)
def create_timeline(payload: VideoTimelineCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = VideoTimeline(user_id=user.id, title=payload.title)
    db.add(timeline)
    db.commit()
    db.refresh(timeline)
    return timeline


@router.get("", response_model=list[VideoTimelineRead])
def list_timelines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(VideoTimeline).filter(VideoTimeline.user_id == user.id).order_by(VideoTimeline.updated_at.desc()).all()


@router.get("/{timeline_id}", response_model=VideoTimelineDetail)
def get_timeline(timeline_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_timeline(db, timeline_id, user)


@router.delete("/{timeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timeline(timeline_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = _get_owned_timeline(db, timeline_id, user)
    db.delete(timeline)
    db.commit()


@router.post("/{timeline_id}/clips", response_model=VideoTimelineClipRead, status_code=status.HTTP_201_CREATED)
def add_clip(
    timeline_id: uuid.UUID,
    payload: VideoTimelineClipCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    timeline = _get_owned_timeline(db, timeline_id, user)
    get_owned_video(db, payload.video_id, user)  # 404s if not owned

    next_index = len(timeline.clips)
    clip = VideoTimelineClip(
        timeline_id=timeline_id,
        video_id=payload.video_id,
        clip_index=next_index,
        trim_start_seconds=payload.trim_start_seconds,
        trim_end_seconds=payload.trim_end_seconds,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


@router.delete("/{timeline_id}/clips/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_clip(
    timeline_id: uuid.UUID, clip_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    clip = _get_owned_clip(db, timeline_id, clip_id, user)
    db.delete(clip)
    db.commit()


@router.post("/{timeline_id}/export", response_model=VideoTimelineExportRead, status_code=status.HTTP_201_CREATED)
def export_timeline(timeline_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = _get_owned_timeline(db, timeline_id, user)
    if not timeline.clips:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Timeline has no clips to export.")

    clips_payload = []
    for clip in timeline.clips:
        video = get_owned_video(db, clip.video_id, user)
        clips_payload.append(
            {
                "storage_path": video.storage_path,
                "trim_start_seconds": clip.trim_start_seconds,
                "trim_end_seconds": clip.trim_end_seconds,
            }
        )

    job = VideoTimelineExportJob(user_id=user.id, timeline_id=timeline_id)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_timeline_export_job(str(job.id), str(user.id), clips_payload)
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch timeline export process: {exc}"
        db.commit()

    return job


@router.get("/exports/{job_id}", response_model=VideoTimelineExportRead)
def get_export_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_export_job(db, job_id, user)


@router.post("/exports/{job_id}/cancel", response_model=VideoTimelineExportRead)
def cancel_export_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = _get_owned_export_job(db, job_id, user)
    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}")

    if job.pid is not None:
        cancel_timeline_export_job(job.pid)

    job.status = "CANCELLED"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
