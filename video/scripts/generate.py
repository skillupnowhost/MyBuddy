#!/usr/bin/env python
"""Standalone text-to-video generation job runner.

Deliberately independent of the backend's `app` package — same reasoning as
imagegen/scripts/generate.py and training/scripts/train_lora.py: this is meant to be a
separately deployable unit (possibly on a different, GPU-equipped machine than the one
running the API). It talks to Postgres only to report its own status and to record the
generated video, via plain SQL, not the backend's ORM models.

Usage:
    python generate.py --job-id <uuid> --user-id <uuid> --prompt "..." --width 256
                        --height 256 --num-frames 16 --fps 8 --steps 25
                        --storage-dir <path> --database-url <url>
"""
import argparse
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    # video_id is a UUID column; a plain string bind needs an explicit cast or Postgres
    # rejects it as "column is of type uuid but expression is of type text" (same reasoning
    # as imagegen/scripts/generate.py's image_id cast).
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "video_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE video_generation_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def save_generated_video(
    engine, user_id: str, storage_dir: str, video_path: str, width: int, height: int, num_frames: int, fps: int
) -> str:
    """Moves the encoded MP4 into the same storage layout convention as
    backend/app/services/storage.py::_save (storage_dir/videos/user_id/<random>.mp4), then
    records it as a `videos` row via raw SQL, exactly like imagegen/scripts/generate.py does
    for `images`."""
    user_dir = os.path.join(storage_dir, "videos", user_id)
    os.makedirs(user_dir, exist_ok=True)
    video_id = uuid.uuid4()
    final_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    os.replace(video_path, final_path)
    size_bytes = os.path.getsize(final_path)
    duration_seconds = num_frames / fps

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (id, user_id, storage_path, content_type, width, height, "
                "duration_seconds, size_bytes, created_at) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :storage_path, :content_type, "
                ":width, :height, :duration_seconds, :size_bytes, now())"
            ),
            {
                "id": str(video_id),
                "user_id": user_id,
                "storage_path": final_path,
                "content_type": "video/mp4",
                "width": width,
                "height": height,
                "duration_seconds": duration_seconds,
                "size_bytes": size_bytes,
            },
        )
    return str(video_id)


def run_generation(args) -> str:
    """Real text-to-video generation via diffusers. Only reached if torch/diffusers/
    transformers/accelerate/imageio are actually installed (see video/requirements.txt) — on
    this project's primary dev machine (no GPU) that import deliberately fails, and the
    caller reports that clearly rather than pretending to generate anything. Returns the path
    to a temporary encoded MP4 (moved into permanent storage by the caller)."""
    import tempfile

    import torch
    from diffusers import DiffusionPipeline
    from diffusers.utils import export_to_video

    pipe = DiffusionPipeline.from_pretrained(args.model, torch_dtype=torch.float32)
    pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

    generator = None
    if args.seed is not None:
        generator = torch.Generator(device=pipe.device).manual_seed(args.seed)

    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        num_frames=args.num_frames,
        height=args.height,
        width=args.width,
        num_inference_steps=args.steps,
        generator=generator,
    )
    frames = result.frames[0]

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    export_to_video(frames, temp_path, fps=args.fps)
    return temp_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--model", default="damo-vilab/text-to-video-ms-1.7b")
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    engine = create_engine(
        args.database_url,
        connect_args={"connect_timeout": 2},
        pool_timeout=5,
    )
    try:
        update_job(engine, args.job_id, status="RUNNING")
    except Exception as exc:  # noqa: BLE001 - fail fast rather than hanging on a missing local DB
        message = f"Could not connect to the database to start generation: {exc}"
        print(message, file=sys.stderr)
        return 1

    try:
        temp_video_path = run_generation(args)
        video_id = save_generated_video(
            engine, args.user_id, args.storage_dir, temp_video_path, args.width, args.height, args.num_frames, args.fps
        )
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            video_id=video_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Video generation dependencies not installed: {exc}. "
            "Run 'pip install -r video/requirements.txt' before starting a generation job."
        )
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1
    except MemoryError:
        # Expected on this project's primary dev machine (no GPU, ~7GB RAM) — see
        # video/README.md's "Hardware reality check". Loading a ~1.7B-parameter diffusion
        # model at float32 needs several GB just for weights; report that plainly instead of
        # a raw traceback ending in "MemoryError" with no context.
        message = (
            f"Ran out of memory loading '{args.model}'. Text-to-video models need far more "
            "RAM (or a GPU with enough VRAM) than this machine has available — see "
            "video/README.md's hardware note. This isn't fixable by retrying; it needs "
            "more RAM/VRAM or a smaller model."
        )
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - any generation failure must be reported, not raised into the void
        message = f"{exc}\n{traceback.format_exc()}"[:4000]
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
