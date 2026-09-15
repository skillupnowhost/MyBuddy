#!/usr/bin/env python
"""Standalone video editing job runner (background removal / green screen, object removal).

Deliberately independent of the backend's `app` package and of generate.py in this same
directory — same reasoning as imagegen/scripts/edit_image.py not importing generate.py: each
subprocess script is self-contained and independently runnable. Talks to Postgres only to
report its own status and to record the result video, via plain SQL, not the backend's ORM.

Two operations, two very different hardware stories:
- REMOVE_BACKGROUND uses rembg (CPU-fast, no GPU dependency) — the one video-track
  operation in this repo that actually completes on CPU-only hardware, given video/.venv is
  provisioned (imageio + rembg, no torch/diffusers needed for this path).
- REMOVE_OBJECT reuses the SD inpainting pipeline (same as imagegen/edit_image.py's INPAINT),
  applied identically to every frame with one static mask — GPU-heavy, same hardware caveat
  as generate.py. There is no per-frame mask tracking: a moving object needs a moving mask,
  which isn't built (spec §21's "maintaining temporal consistency" is explicitly not
  attempted here — see video/README.md).

Usage:
    python edit_video.py --job-id <uuid> --user-id <uuid> --operation REMOVE_BACKGROUND \
        --source-video-path <path> --background-color "#00b140" --bg-removal-model u2net \
        --storage-dir <path> --database-url <url>
    python edit_video.py --job-id <uuid> --user-id <uuid> --operation REMOVE_OBJECT \
        --source-video-path <path> --mask-image-path <path> --prompt "empty street" \
        --inpaint-model runwayml/stable-diffusion-inpainting --steps 20 \
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
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "result_video_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE video_edit_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def save_result_video(
    engine, user_id: str, storage_dir: str, video_path: str, width: int, height: int, duration_seconds: float
) -> str:
    """Same storage/insert convention as generate.py's save_generated_video."""
    user_dir = os.path.join(storage_dir, "videos", user_id)
    os.makedirs(user_dir, exist_ok=True)
    video_id = uuid.uuid4()
    final_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    os.replace(video_path, final_path)
    size_bytes = os.path.getsize(final_path)

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


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def run_remove_background(args) -> tuple[str, int, int, float]:
    """Reads the source video frame by frame, removes the background from each frame via
    rembg, composites the result onto a solid background color, and re-encodes. Only reached
    if imageio/rembg (and rembg's onnxruntime dependency) are actually installed (see
    video/requirements.txt) — reports that clearly otherwise. Returns
    (temp_output_path, width, height, duration_seconds)."""
    import tempfile

    import imageio
    import numpy as np
    from PIL import Image
    from rembg import new_session, remove

    bg_rgb = _hex_to_rgb(args.background_color)
    session = new_session(args.bg_removal_model)

    reader = imageio.get_reader(args.source_video_path)
    meta = reader.get_meta_data()
    fps = meta.get("fps", 24)

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = imageio.get_writer(temp_path, fps=fps)
    width = height = 0
    frame_count = 0
    try:
        for frame in reader:
            source_frame = Image.fromarray(frame).convert("RGB")
            width, height = source_frame.size
            cutout = remove(source_frame, session=session)  # RGBA
            background = Image.new("RGB", cutout.size, bg_rgb)
            background.paste(cutout, mask=cutout.split()[3])
            writer.append_data(np.array(background))
            frame_count += 1
    finally:
        writer.close()
        reader.close()

    duration_seconds = frame_count / fps if fps else 0.0
    return temp_path, width, height, duration_seconds


def run_remove_object(args) -> tuple[str, int, int, float]:
    """Reads the source video frame by frame and inpaints the same static mask on every
    frame via a Stable Diffusion inpainting pipeline (same model/API as
    imagegen/edit_image.py's run_inpaint). Only reached if torch/diffusers are actually
    installed. Returns (temp_output_path, width, height, duration_seconds)."""
    import tempfile

    import imageio
    import numpy as np
    import torch
    from diffusers import AutoPipelineForInpainting
    from PIL import Image

    pipe = AutoPipelineForInpainting.from_pretrained(args.inpaint_model, torch_dtype=torch.float32)
    pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
    mask = Image.open(args.mask_image_path).convert("L")

    reader = imageio.get_reader(args.source_video_path)
    meta = reader.get_meta_data()
    fps = meta.get("fps", 24)

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = imageio.get_writer(temp_path, fps=fps)
    width = height = 0
    frame_count = 0
    try:
        for frame in reader:
            source_frame = Image.fromarray(frame).convert("RGB")
            width, height = source_frame.size
            result = pipe(
                prompt=args.prompt,
                negative_prompt=args.negative_prompt,
                image=source_frame,
                mask_image=mask.resize(source_frame.size),
                num_inference_steps=args.steps,
            )
            writer.append_data(np.array(result.images[0].convert("RGB")))
            frame_count += 1
    finally:
        writer.close()
        reader.close()

    duration_seconds = frame_count / fps if fps else 0.0
    return temp_path, width, height, duration_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--operation", required=True, choices=["REMOVE_BACKGROUND", "REMOVE_OBJECT"])
    parser.add_argument("--source-video-path", required=True)
    parser.add_argument("--background-color", default="#00b140")
    parser.add_argument("--bg-removal-model", default="u2net")
    parser.add_argument("--mask-image-path", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--inpaint-model", default="runwayml/stable-diffusion-inpainting")
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    if args.operation == "REMOVE_OBJECT" and (not args.mask_image_path or not args.prompt):
        print("REMOVE_OBJECT requires --mask-image-path and --prompt.", file=sys.stderr)
        return 1

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        if args.operation == "REMOVE_OBJECT":
            temp_path, width, height, duration_seconds = run_remove_object(args)
        else:
            temp_path, width, height, duration_seconds = run_remove_background(args)
        video_id = save_result_video(engine, args.user_id, args.storage_dir, temp_path, width, height, duration_seconds)
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            result_video_id=video_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Video editing dependencies not installed: {exc}. "
            "Run 'pip install -r video/requirements.txt' before starting an edit job."
        )
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - any edit failure must be reported, not raised into the void
        message = f"{exc}\n{traceback.format_exc()}"[:4000]
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
