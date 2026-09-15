#!/usr/bin/env python
"""Standalone video editing job runner (background removal / green screen, object removal).

Deliberately independent of the backend's `app` package and of generate.py in this same
directory — same reasoning as imagegen/scripts/edit_image.py not importing generate.py: each
subprocess script is self-contained and independently runnable. Talks to Postgres only to
report its own status and to record the result video, via plain SQL, not the backend's ORM.

Three operations, two very different hardware stories:
- REMOVE_BACKGROUND and REPLACE_ENVIRONMENT both use rembg (CPU-fast, no GPU dependency) —
  the video-track operations in this repo that actually complete on CPU-only hardware, given
  video/.venv is provisioned (imageio + rembg, no torch/diffusers needed for this path).
  REPLACE_ENVIRONMENT is the same per-frame segmentation composited onto a provided
  background image instead of a solid color (spec §23).
- REMOVE_OBJECT reuses the SD inpainting pipeline (same as imagegen/edit_image.py's INPAINT),
  applied identically to every frame with one static mask — GPU-heavy, same hardware caveat
  as generate.py. There is no per-frame mask tracking: a moving object needs a moving mask,
  which isn't built (spec §21's "maintaining temporal consistency" is explicitly not
  attempted here — see video/README.md).

Usage:
    python edit_video.py --job-id <uuid> --user-id <uuid> --operation REMOVE_BACKGROUND \
        --source-video-path <path> --background-color "#00b140" --bg-removal-model u2net \
        --storage-dir <path> --database-url <url>
    python edit_video.py --job-id <uuid> --user-id <uuid> --operation REPLACE_ENVIRONMENT \
        --source-video-path <path> --background-image-path <path> --bg-removal-model u2net \
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


def run_replace_environment(args) -> tuple[str, int, int, float]:
    """Same per-frame rembg segmentation as run_remove_background, but composites the
    foreground cutout onto a provided background image (resized to fill the frame) instead
    of a solid color — spec §23 AI Environment Replacement. Still CPU-fast, no GPU needed."""
    import tempfile

    import imageio
    import numpy as np
    from PIL import Image
    from rembg import new_session, remove

    background_source = Image.open(args.background_image_path).convert("RGB")
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
            background = background_source.resize((width, height))
            background.paste(cutout, mask=cutout.split()[3])
            writer.append_data(np.array(background))
            frame_count += 1
    finally:
        writer.close()
        reader.close()

    duration_seconds = frame_count / fps if fps else 0.0
    return temp_path, width, height, duration_seconds


# Classical per-frame color grading (spec §24/§29): a fixed preset library, not arbitrary
# custom-LUT support. Each value is a delta/multiplier applied via PIL's ImageEnhance
# (brightness/contrast/saturation, 1.0 = unchanged) plus a manual (red, blue) channel shift
# for warm/cool temperature — no ML model, honestly labeled as classical grading. Keep this
# dict's keys in sync with backend/app/schemas/video_edit.py's ColorGradePreset literal.
_COLOR_GRADE_PRESETS = {
    "CINEMATIC": {"brightness": 0.95, "contrast": 1.15, "saturation": 0.9, "temperature": (5, -5), "grayscale": False},
    "VINTAGE": {"brightness": 1.0, "contrast": 0.9, "saturation": 0.7, "temperature": (12, -12), "grayscale": False},
    "WARM": {"brightness": 1.0, "contrast": 1.0, "saturation": 1.05, "temperature": (15, -10), "grayscale": False},
    "COLD": {"brightness": 1.0, "contrast": 1.0, "saturation": 1.0, "temperature": (-15, 15), "grayscale": False},
    "BLACK_AND_WHITE": {"brightness": 1.0, "contrast": 1.05, "saturation": 0.0, "temperature": (0, 0), "grayscale": True},
    "NOIR": {"brightness": 0.85, "contrast": 1.4, "saturation": 0.0, "temperature": (0, 0), "grayscale": True},
    "VIVID": {"brightness": 1.05, "contrast": 1.15, "saturation": 1.4, "temperature": (0, 0), "grayscale": False},
    "MUTED": {"brightness": 1.0, "contrast": 0.9, "saturation": 0.55, "temperature": (0, 0), "grayscale": False},
}


def _apply_color_grade(frame_image, preset: dict):
    import numpy as np
    from PIL import Image, ImageEnhance

    graded = ImageEnhance.Brightness(frame_image).enhance(preset["brightness"])
    graded = ImageEnhance.Contrast(graded).enhance(preset["contrast"])
    graded = ImageEnhance.Color(graded).enhance(preset["saturation"])

    red_shift, blue_shift = preset["temperature"]
    if red_shift or blue_shift:
        array = np.array(graded).astype(np.int16)
        array[:, :, 0] = np.clip(array[:, :, 0] + red_shift, 0, 255)
        array[:, :, 2] = np.clip(array[:, :, 2] + blue_shift, 0, 255)
        graded = Image.fromarray(array.astype(np.uint8))

    if preset["grayscale"]:
        graded = graded.convert("L").convert("RGB")

    return graded


def run_color_grade(args) -> tuple[str, int, int, float]:
    """Applies one fixed color-grade preset to every frame — classical image processing
    (PIL ImageEnhance + a numpy channel shift), no ML model, so this is CPU-fast like
    REMOVE_BACKGROUND/REPLACE_ENVIRONMENT rather than GPU-heavy like generation/REMOVE_OBJECT."""
    import tempfile

    import imageio
    import numpy as np
    from PIL import Image

    preset = _COLOR_GRADE_PRESETS[args.color_preset]

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
            graded = _apply_color_grade(source_frame, preset)
            writer.append_data(np.array(graded))
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


# Classical particle-simulation VFX overlays (spec §17 VFX Engine) — plain Euler physics
# (position += velocity, velocity += gravity) rendered via PIL ImageDraw, no ML model at all.
# Honestly labeled as classical simulation, not a neural VFX generator. Keep this dict's keys
# in sync with backend/app/schemas/video_edit.py's VfxType literal.
_VFX_PARTICLE_PRESETS = {
    "RAIN": {"count": 150, "color": (200, 220, 255), "gravity": 0.0, "spawn_top": True, "fades": False},
    "SNOW": {"count": 80, "color": (255, 255, 255), "gravity": 0.0, "spawn_top": True, "fades": False},
    "SPARKS": {"count": 60, "color": (255, 170, 60), "gravity": 0.35, "spawn_top": False, "fades": True},
}


def _spawn_particle(vfx_type: str, width: int, height: int, random_module):
    if vfx_type == "RAIN":
        return {
            "x": random_module.uniform(0, width),
            "y": random_module.uniform(-height, 0),
            "vx": random_module.uniform(-1, -3),
            "vy": random_module.uniform(18, 28),
            "life": None,
        }
    if vfx_type == "SNOW":
        return {
            "x": random_module.uniform(0, width),
            "y": random_module.uniform(-height, 0),
            "vx": random_module.uniform(-1.5, 1.5),
            "vy": random_module.uniform(1.5, 4),
            "life": None,
        }
    # SPARKS: burst upward from the bottom edge, gravity pulls them back down, fade with age.
    max_life = random_module.randint(15, 35)
    return {
        "x": random_module.uniform(0, width),
        "y": float(height),
        "vx": random_module.uniform(-3, 3),
        "vy": random_module.uniform(-9, -4),
        "life": max_life,
        "max_life": max_life,
    }


def run_add_vfx(args) -> tuple[str, int, int, float]:
    """Overlays a classical particle simulation (rain/snow/sparks) on every frame — see
    _VFX_PARTICLE_PRESETS. CPU-fast like REMOVE_BACKGROUND/COLOR_GRADE, no ML model."""
    import random
    import tempfile

    import imageio
    import numpy as np
    from PIL import Image, ImageDraw

    preset = _VFX_PARTICLE_PRESETS[args.vfx_type]

    reader = imageio.get_reader(args.source_video_path)
    meta = reader.get_meta_data()
    fps = meta.get("fps", 24)

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = imageio.get_writer(temp_path, fps=fps)
    width = height = 0
    frame_count = 0
    particles: list[dict] = []
    try:
        for frame in reader:
            source_frame = Image.fromarray(frame).convert("RGB")
            width, height = source_frame.size

            if not particles:
                particles = [_spawn_particle(args.vfx_type, width, height, random) for _ in range(preset["count"])]

            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for i, particle in enumerate(particles):
                particle["x"] += particle["vx"]
                particle["y"] += particle["vy"]
                particle["vy"] += preset["gravity"]

                if preset["fades"]:
                    particle["life"] -= 1
                    alpha = max(0, int(255 * (particle["life"] / particle["max_life"])))
                    out_of_bounds = particle["life"] <= 0 or particle["y"] > height
                else:
                    alpha = 200
                    out_of_bounds = particle["y"] > height or particle["y"] < -20 or particle["x"] < -20 or particle["x"] > width + 20

                if out_of_bounds:
                    particles[i] = _spawn_particle(args.vfx_type, width, height, random)
                    continue

                color = (*preset["color"], alpha)
                if args.vfx_type == "RAIN":
                    draw.line(
                        [(particle["x"], particle["y"]), (particle["x"] + particle["vx"], particle["y"] - particle["vy"] * 0.4)],
                        fill=color, width=1,
                    )
                else:
                    radius = 2 if args.vfx_type == "SNOW" else 1.5
                    draw.ellipse(
                        [particle["x"] - radius, particle["y"] - radius, particle["x"] + radius, particle["y"] + radius],
                        fill=color,
                    )

            composited = Image.alpha_composite(source_frame.convert("RGBA"), overlay).convert("RGB")
            writer.append_data(np.array(composited))
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
    parser.add_argument(
        "--operation",
        required=True,
        choices=["REMOVE_BACKGROUND", "REMOVE_OBJECT", "REPLACE_ENVIRONMENT", "COLOR_GRADE", "ADD_VFX"],
    )
    parser.add_argument("--source-video-path", required=True)
    parser.add_argument("--background-color", default="#00b140")
    parser.add_argument("--background-image-path", default=None)
    parser.add_argument("--bg-removal-model", default="u2net")
    parser.add_argument("--mask-image-path", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--inpaint-model", default="runwayml/stable-diffusion-inpainting")
    parser.add_argument("--color-preset", default=None, choices=list(_COLOR_GRADE_PRESETS))
    parser.add_argument("--vfx-type", default=None, choices=list(_VFX_PARTICLE_PRESETS))
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    if args.operation == "REMOVE_OBJECT" and (not args.mask_image_path or not args.prompt):
        print("REMOVE_OBJECT requires --mask-image-path and --prompt.", file=sys.stderr)
        return 1
    if args.operation == "REPLACE_ENVIRONMENT" and not args.background_image_path:
        print("REPLACE_ENVIRONMENT requires --background-image-path.", file=sys.stderr)
        return 1
    if args.operation == "COLOR_GRADE" and not args.color_preset:
        print("COLOR_GRADE requires --color-preset.", file=sys.stderr)
        return 1
    if args.operation == "ADD_VFX" and not args.vfx_type:
        print("ADD_VFX requires --vfx-type.", file=sys.stderr)
        return 1

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        if args.operation == "REMOVE_OBJECT":
            temp_path, width, height, duration_seconds = run_remove_object(args)
        elif args.operation == "REPLACE_ENVIRONMENT":
            temp_path, width, height, duration_seconds = run_replace_environment(args)
        elif args.operation == "COLOR_GRADE":
            temp_path, width, height, duration_seconds = run_color_grade(args)
        elif args.operation == "ADD_VFX":
            temp_path, width, height, duration_seconds = run_add_vfx(args)
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
