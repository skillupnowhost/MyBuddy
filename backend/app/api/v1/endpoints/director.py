import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.characters import get_owned_character
from app.api.v1.endpoints.world_bibles import get_owned_world_bible
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.storyboard import Storyboard
from app.db.models.storyboard_shot import StoryboardShot
from app.db.models.user import User
from app.db.models.video_generation_job import VideoGenerationJob
from app.schemas.director import DirectorFilmCreate
from app.schemas.storyboard import StoryboardDetail
from app.services.consistency_service import character_guidance, world_guidance
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.model_router import get_model_router
from app.services.script_service import generate_script
from app.services.storyboard_service import StoryboardGenerationError, generate_storyboard
from app.services.video_generation_service import launch_video_generation_job

settings = get_settings()
router = APIRouter(prefix="/director", tags=["director"])


@router.post("/films", response_model=StoryboardDetail, status_code=status.HTTP_201_CREATED)
async def create_film(
    payload: DirectorFilmCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    """MyBuddy Director (spec §5-6): idea -> script -> shot-by-shot storyboard -> (optionally)
    a video generation job kicked off for every shot. Orchestrates entirely by calling the
    same service functions the Storyboard/Video-generation endpoints already use — no new
    generation pathway, no new data model on top of Storyboard/StoryboardShot/
    VideoGenerationJob. Same GPU-hardware caveat as calling /api/v1/video-generation
    directly: the orchestration is real, the pixels aren't verified on this machine."""
    characters = [get_owned_character(db, cid, user) for cid in payload.character_ids]
    world_bible = get_owned_world_bible(db, payload.world_bible_id, user) if payload.world_bible_id else None
    guidance = " ".join(filter(None, [character_guidance(characters), world_guidance(world_bible)]))

    model = get_model_router().select(db, "TEXT").base_model

    script = await generate_script(llm_client, model, payload.idea, settings.storyboard_max_shots)

    try:
        shots = await generate_storyboard(
            llm_client, model, script, settings.storyboard_max_shots, settings.storyboard_max_retries, guidance
        )
    except StoryboardGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    storyboard = Storyboard(
        user_id=user.id,
        title=payload.title or "Untitled film",
        script=script,
        character_ids=[str(cid) for cid in payload.character_ids],
        world_bible_id=payload.world_bible_id,
    )
    db.add(storyboard)
    db.flush()

    shot_rows = [
        StoryboardShot(storyboard_id=storyboard.id, shot_index=i, **shot.model_dump()) for i, shot in enumerate(shots)
    ]
    db.add_all(shot_rows)
    db.commit()
    db.refresh(storyboard)

    if payload.generate_video:
        for shot_row in storyboard.shots:
            job_id = _create_and_launch_shot_video_job(db, user.id, shot_row.generation_prompt)
            shot_row.video_generation_job_id = job_id
        db.commit()
        db.refresh(storyboard)

    return storyboard


def _create_and_launch_shot_video_job(db: Session, user_id: uuid.UUID, prompt: str) -> uuid.UUID:
    """Same VideoGenerationJob creation + launch as video_generation.create_video_generation_job
    and storyboard.generate_shot_video, using settings defaults throughout — Director doesn't
    expose per-shot resolution/step overrides, unlike calling either endpoint directly."""
    job = VideoGenerationJob(
        user_id=user_id,
        prompt=prompt,
        width=settings.video_gen_default_width,
        height=settings.video_gen_default_height,
        num_frames=settings.video_gen_default_num_frames,
        fps=settings.video_gen_fps,
        steps=settings.video_gen_default_steps,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        proc = launch_video_generation_job(
            str(job.id),
            str(user_id),
            prompt,
            None,
            settings.video_gen_default_width,
            settings.video_gen_default_height,
            settings.video_gen_default_num_frames,
            settings.video_gen_fps,
            settings.video_gen_default_steps,
            None,
        )
        job.pid = getattr(proc, "pid", None)
        db.commit()
    except OSError as exc:
        job.status = "FAILED"
        job.error_message = f"Could not launch video generation process: {exc}"
        db.commit()

    return job.id
