import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.camera_plans import get_owned_camera_plan
from app.api.v1.endpoints.characters import get_owned_character
from app.api.v1.endpoints.world_bibles import get_owned_world_bible
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.storyboard import Storyboard
from app.db.models.storyboard_shot import StoryboardShot
from app.db.models.user import User
from app.db.models.video_generation_job import VideoGenerationJob
from app.schemas.storyboard import (
    ShotVideoGenerateRequest,
    StoryboardDetail,
    StoryboardGenerateRequest,
    StoryboardRead,
)
from app.schemas.video_generation import VideoGenerationRead
from app.services.camera_plan_service import describe_camera_plan
from app.services.consistency_service import character_guidance, world_guidance
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.model_router import get_model_router
from app.services.storyboard_service import StoryboardGenerationError, generate_storyboard
from app.services.video_generation_service import launch_video_generation_job

settings = get_settings()
router = APIRouter(prefix="/storyboards", tags=["storyboards"])


def _get_owned_storyboard(db: Session, storyboard_id: uuid.UUID, user: User) -> Storyboard:
    storyboard = db.get(Storyboard, storyboard_id)
    if storyboard is None or storyboard.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard not found")
    return storyboard


def _get_owned_shot(db: Session, storyboard_id: uuid.UUID, shot_id: uuid.UUID, user: User) -> StoryboardShot:
    _get_owned_storyboard(db, storyboard_id, user)  # 404s if the storyboard itself isn't owned
    shot = db.get(StoryboardShot, shot_id)
    if shot is None or shot.storyboard_id != storyboard_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard shot not found")
    return shot


@router.post("", response_model=StoryboardDetail, status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    payload: StoryboardGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    characters = [get_owned_character(db, cid, user) for cid in payload.character_ids]
    world_bible = get_owned_world_bible(db, payload.world_bible_id, user) if payload.world_bible_id else None
    guidance = " ".join(filter(None, [character_guidance(characters), world_guidance(world_bible)]))

    model = get_model_router().select(db, "TEXT").base_model
    try:
        shots = await generate_storyboard(
            llm_client,
            model,
            payload.script,
            settings.storyboard_max_shots,
            settings.storyboard_max_retries,
            guidance,
        )
    except StoryboardGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    storyboard = Storyboard(
        user_id=user.id,
        title=payload.title or "Untitled storyboard",
        script=payload.script,
        character_ids=[str(cid) for cid in payload.character_ids],
        world_bible_id=payload.world_bible_id,
    )
    db.add(storyboard)
    db.flush()  # assigns storyboard.id without committing yet, so shots can reference it

    db.add_all(
        [
            StoryboardShot(storyboard_id=storyboard.id, shot_index=i, **shot.model_dump())
            for i, shot in enumerate(shots)
        ]
    )
    db.commit()
    db.refresh(storyboard)
    return storyboard


@router.get("", response_model=list[StoryboardRead])
def list_storyboards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Storyboard).filter(Storyboard.user_id == user.id).order_by(Storyboard.created_at.desc()).all()


@router.get("/{storyboard_id}", response_model=StoryboardDetail)
def get_storyboard(storyboard_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_storyboard(db, storyboard_id, user)


@router.post(
    "/{storyboard_id}/shots/{shot_id}/generate-video",
    response_model=VideoGenerationRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_shot_video(
    storyboard_id: uuid.UUID,
    shot_id: uuid.UUID,
    payload: ShotVideoGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bridges the planning layer (Storyboard/CameraPlan) to actual generation (MyBuddy
    Video): launches a VideoGenerationJob from the shot's generation_prompt, optionally
    enriched with a CameraPlan's rendered description, and links the job back to the shot.
    Same hardware caveat as /api/v1/video-generation directly — this is real, working
    plumbing that doesn't produce a usable clip on this project's CPU-only dev machine."""
    shot = _get_owned_shot(db, storyboard_id, shot_id, user)

    if payload.width > settings.video_gen_max_width or payload.height > settings.video_gen_max_height:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"width/height must not exceed {settings.video_gen_max_width}x{settings.video_gen_max_height}.",
        )
    if payload.num_frames > settings.video_gen_max_num_frames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"num_frames must not exceed {settings.video_gen_max_num_frames}.",
        )
    if payload.steps > settings.video_gen_max_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"steps must not exceed {settings.video_gen_max_steps}."
        )

    prompt = shot.generation_prompt
    if payload.camera_plan_id is not None:
        camera_plan = get_owned_camera_plan(db, payload.camera_plan_id, user)
        prompt = f"{prompt}, {describe_camera_plan(camera_plan)}"

    job = VideoGenerationJob(
        user_id=user.id,
        prompt=prompt,
        width=payload.width,
        height=payload.height,
        num_frames=payload.num_frames,
        fps=settings.video_gen_fps,
        steps=payload.steps,
        seed=payload.seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_video_generation_job(
            str(job.id), str(user.id), prompt, None, payload.width, payload.height,
            payload.num_frames, settings.video_gen_fps, payload.steps, payload.seed,
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch video generation process: {exc}"
        db.commit()

    shot.video_generation_job_id = job.id
    db.commit()
    return job


@router.delete("/{storyboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storyboard(storyboard_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    storyboard = _get_owned_storyboard(db, storyboard_id, user)
    db.delete(storyboard)
    db.commit()
