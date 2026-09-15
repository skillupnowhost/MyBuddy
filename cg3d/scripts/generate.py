#!/usr/bin/env python
"""Standalone text/image-to-3D generation job runner.

Deliberately independent of the backend's `app` package — same reasoning as
imagegen/scripts/generate.py and video/scripts/generate.py: meant to be a separately
deployable unit (possibly on a different, GPU-equipped machine than the one running the
API). Talks to Postgres only to report its own status and to record the generated mesh, via
plain SQL, not the backend's ORM models.

Usage:
    python generate.py --job-id <uuid> --user-id <uuid> --prompt "..." --steps 64
                        --guidance-scale 15.0 --storage-dir <path> --database-url <url>
    python generate.py --job-id <uuid> --user-id <uuid> --source-image-path <path> ...
"""
import argparse
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    # model_3d_id is a UUID column; a plain string bind needs an explicit cast, same
    # reasoning as imagegen/video's image_id/video_id casts.
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "model_3d_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE model_3d_generation_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def save_generated_model(engine, user_id: str, storage_dir: str, obj_path: str) -> str:
    """Moves the exported OBJ into the same storage layout convention as
    backend/app/services/storage.py::_save (storage_dir/models3d/user_id/<random>.obj), then
    records it as a `models_3d` row via raw SQL, same pattern as imagegen/video."""
    user_dir = os.path.join(storage_dir, "models3d", user_id)
    os.makedirs(user_dir, exist_ok=True)
    model_id = uuid.uuid4()
    final_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.obj")
    os.replace(obj_path, final_path)
    size_bytes = os.path.getsize(final_path)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO models_3d (id, user_id, storage_path, format, size_bytes, created_at) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :storage_path, :format, :size_bytes, now())"
            ),
            {
                "id": str(model_id),
                "user_id": user_id,
                "storage_path": final_path,
                "format": "obj",
                "size_bytes": size_bytes,
            },
        )
    return str(model_id)


def run_generation(args) -> str:
    """Real text/image-to-3D generation via diffusers' Shap-E pipelines. Only reached if
    torch/diffusers/transformers/accelerate/trimesh are actually installed (see
    cg3d/requirements.txt) — on this project's primary dev machine (no GPU) that import
    deliberately fails, and the caller reports that clearly. Returns the path to a temporary
    OBJ file (moved into permanent storage by the caller)."""
    import tempfile

    import torch
    from diffusers.utils import export_to_obj

    device = "cuda" if torch.cuda.is_available() else "cpu"
    generator = torch.Generator(device=device).manual_seed(args.seed) if args.seed is not None else None

    if args.source_image_path:
        from diffusers import ShapEImg2ImgPipeline
        from PIL import Image as PILImage

        pipe = ShapEImg2ImgPipeline.from_pretrained(args.image_model, torch_dtype=torch.float32).to(device)
        source_image = PILImage.open(args.source_image_path).convert("RGB")
        result = pipe(
            image=source_image,
            guidance_scale=args.guidance_scale,
            num_inference_steps=args.steps,
            frame_size=256,
            output_type="mesh",
            generator=generator,
        )
    else:
        from diffusers import ShapEPipeline

        pipe = ShapEPipeline.from_pretrained(args.text_model, torch_dtype=torch.float32).to(device)
        result = pipe(
            prompt=args.prompt,
            guidance_scale=args.guidance_scale,
            num_inference_steps=args.steps,
            frame_size=256,
            output_type="mesh",
            generator=generator,
        )

    mesh = result.images[0]
    fd, temp_path = tempfile.mkstemp(suffix=".obj")
    os.close(fd)
    export_to_obj(mesh, temp_path)
    return temp_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--source-image-path", default=None)
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--guidance-scale", type=float, default=15.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--text-model", default="openai/shap-e")
    parser.add_argument("--image-model", default="openai/shap-e-img2img")
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    if not args.prompt and not args.source_image_path:
        print("Either --prompt or --source-image-path is required.", file=sys.stderr)
        return 1

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        temp_obj_path = run_generation(args)
        model_id = save_generated_model(engine, args.user_id, args.storage_dir, temp_obj_path)
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            model_3d_id=model_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"3D generation dependencies not installed: {exc}. "
            "Run 'pip install -r cg3d/requirements.txt' before starting a generation job."
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
