#!/usr/bin/env python
"""Standalone text-to-image generation job runner.

Deliberately independent of the backend's `app` package — same reasoning as
training/scripts/train_lora.py: this is meant to be a separately deployable unit
(possibly on a different, GPU-equipped machine than the one running the API). It talks to
Postgres only to report its own status and to record the generated image, via plain SQL,
not the backend's ORM models.

Usage:
    python generate.py --job-id <uuid> --user-id <uuid> --prompt "..." --width 512
                        --height 512 --steps 4 --storage-dir <path> --database-url <url>
"""
import argparse
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    # image_id is a UUID column; a plain string bind needs an explicit cast or Postgres
    # rejects it as "column is of type uuid but expression is of type text" (same reasoning
    # as train_lora.py's eval_metrics/JSON cast).
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "image_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE image_generation_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def save_generated_image(engine, user_id: str, storage_dir: str, image_bytes: bytes) -> str:
    """Writes the PNG to disk using the same path convention as
    backend/app/services/storage.py::_save (storage_dir/images/user_id/<random>.png), then
    records it as an `images` row via raw SQL — reusing the Image model/endpoint the backend
    already built for Vision (chat image attachments). Returns the new image id."""
    user_dir = os.path.join(storage_dir, "images", user_id)
    os.makedirs(user_dir, exist_ok=True)
    image_id = uuid.uuid4()
    storage_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.png")
    with open(storage_path, "wb") as f:
        f.write(image_bytes)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO images (id, user_id, storage_path, content_type, size_bytes, created_at) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :storage_path, :content_type, :size_bytes, now())"
            ),
            {
                "id": str(image_id),
                "user_id": user_id,
                "storage_path": storage_path,
                "content_type": "image/png",
                "size_bytes": len(image_bytes),
            },
        )
    return str(image_id)


def run_generation(args) -> bytes:
    """Real text-to-image generation via diffusers. Only reached if torch/diffusers/
    transformers/accelerate are actually installed (see imagegen/requirements.txt) — on this
    project's primary dev machine (no GPU) that import deliberately fails, and the caller
    reports that clearly rather than pretending to generate anything."""
    import io

    import torch
    from diffusers import AutoPipelineForText2Image

    pipe = AutoPipelineForText2Image.from_pretrained(args.model, torch_dtype=torch.float32)
    pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

    generator = None
    if args.seed is not None:
        generator = torch.Generator(device=pipe.device).manual_seed(args.seed)

    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        width=args.width,
        height=args.height,
        num_inference_steps=args.steps,
        guidance_scale=0.0 if "turbo" in args.model.lower() else 7.5,
        generator=generator,
    )
    image = result.images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--model", default="stabilityai/sd-turbo")
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        image_bytes = run_generation(args)
        image_id = save_generated_image(engine, args.user_id, args.storage_dir, image_bytes)
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            image_id=image_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Image generation dependencies not installed: {exc}. "
            "Run 'pip install -r imagegen/requirements.txt' before starting a generation job."
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
