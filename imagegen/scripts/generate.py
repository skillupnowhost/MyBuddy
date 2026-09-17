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

# huggingface_hub's local cache normally hard-links/symlinks each snapshot file back to a
# shared blob store. Creating those links needs either Administrator rights or Developer Mode
# on Windows (SeCreateSymbolicLinkPrivilege) — without it, downloads fail part-way through
# with "[WinError 1314] A required privilege is not held by the client". Disabling symlinks
# makes it copy the file instead, which needs no special privilege at the cost of a bit more
# disk space. Must be set before huggingface_hub/diffusers/transformers are imported anywhere
# in this process, so it's set here at module load time.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

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

    # Prefer the fp16-variant safetensors weights when a repo publishes them (smaller download,
    # and safetensors mmaps the file instead of reading it whole into memory) even though we
    # compute in float32 — this machine has only ~8GB RAM, and sd-turbo's fp32 .bin checkpoint
    # (~3.2GB, read fully into memory by diffusers' legacy-checkpoint loader) was enough on its
    # own to OOM. CPU inference in float16 itself isn't reliable (many CPU kernels don't
    # implement Half), so we still upcast to float32 for the actual computation.
    #
    # Not every model publishes fp16-variant or even safetensors files at all (e.g.
    # segmind/tiny-sd ships only plain .bin) — diffusers raises OSError for a missing
    # repo/revision but ValueError for "no fp16-variant files", so both are caught as "fall
    # back to whatever this repo actually has", without forcing a format it doesn't provide.
    try:
        pipe = AutoPipelineForText2Image.from_pretrained(
            args.model, torch_dtype=torch.float32, variant="fp16", use_safetensors=True
        )
    except (OSError, ValueError):
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
