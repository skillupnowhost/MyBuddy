#!/usr/bin/env python
"""Standalone image editing job runner (inpaint / outpaint / remove_background).

Deliberately independent of the backend's `app` package — same reasoning as
generate.py and training/scripts/train_lora.py: this talks to Postgres only to report its
own status and to read/write `images` rows, via plain SQL, not the backend's ORM models.

Usage:
    python edit_image.py --job-id <uuid> --user-id <uuid> --operation inpaint
                          --source-image-id <uuid> --mask-image-id <uuid> --prompt "..."
                          --storage-dir <path> --database-url <url>
"""
import argparse
import io
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    # result_image_id is a UUID column; a plain string bind needs an explicit cast or
    # Postgres rejects it (same reasoning as generate.py's image_id cast).
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS uuid)" if key == "result_image_id" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE image_edit_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def fetch_image(engine, image_id: str, user_id: str):
    """Returns (storage_path, content_type) for an image owned by user_id, or None if not
    found/not owned — mirrors the ownership check the API already does on write."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT storage_path, content_type FROM images "
                "WHERE id = CAST(:id AS uuid) AND user_id = CAST(:user_id AS uuid)"
            ),
            {"id": image_id, "user_id": user_id},
        ).first()
    return (row.storage_path, row.content_type) if row is not None else None


def save_result_image(engine, user_id: str, storage_dir: str, image_bytes: bytes) -> str:
    """Same path/DB-insert convention as generate.py::save_generated_image, duplicated
    locally — this repo's standalone scripts are each self-contained by convention."""
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


def _load_inpaint_pipeline(model: str):
    import torch
    from diffusers import AutoPipelineForInpainting

    pipe = AutoPipelineForInpainting.from_pretrained(model, torch_dtype=torch.float32)
    return pipe.to("cuda" if torch.cuda.is_available() else "cpu")


def run_inpaint(args, source_path: str, mask_path: str):
    """Mask convention: white = regenerate this area, black = keep the original pixels —
    the standard diffusers inpainting convention, also documented for the frontend's mask
    painter."""
    import torch
    from PIL import Image

    pipe = _load_inpaint_pipeline(args.model)
    source = Image.open(source_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")

    generator = torch.Generator(device=pipe.device).manual_seed(args.seed) if args.seed is not None else None
    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        image=source,
        mask_image=mask,
        num_inference_steps=args.steps,
        generator=generator,
    )
    return result.images[0]


def run_outpaint(args, source_path: str):
    """Extends the canvas by the requested padding on each side, then reuses the same
    inpainting pipeline with a programmatically generated mask (white over the new padding,
    black over the original) — no user-drawn mask needed."""
    import torch
    from PIL import Image

    source = Image.open(source_path).convert("RGB")
    w, h = source.size
    new_w = w + args.outpaint_left + args.outpaint_right
    new_h = h + args.outpaint_top + args.outpaint_bottom

    canvas = Image.new("RGB", (new_w, new_h), color=(128, 128, 128))
    canvas.paste(source, (args.outpaint_left, args.outpaint_top))

    mask = Image.new("L", (new_w, new_h), color=255)  # 255 = regenerate everywhere...
    mask.paste(0, (args.outpaint_left, args.outpaint_top, args.outpaint_left + w, args.outpaint_top + h))  # ...except the original

    pipe = _load_inpaint_pipeline(args.model)
    generator = torch.Generator(device=pipe.device).manual_seed(args.seed) if args.seed is not None else None
    result = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        image=canvas,
        mask_image=mask,
        num_inference_steps=args.steps,
        generator=generator,
    )
    return result.images[0]


def run_remove_background(args, source_path: str):
    """Only reached if rembg (and its onnxruntime dependency) is installed — see
    imagegen/requirements.txt. Comparatively fast on CPU, unlike the diffusion-based
    inpaint/outpaint paths above."""
    from PIL import Image
    from rembg import new_session, remove

    session = new_session(args.bg_removal_model)
    source = Image.open(source_path).convert("RGBA")
    return remove(source, session=session)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--operation", required=True, choices=["inpaint", "outpaint", "remove_background"])
    parser.add_argument("--source-image-id", required=True)
    parser.add_argument("--mask-image-id", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--outpaint-top", type=int, default=0)
    parser.add_argument("--outpaint-bottom", type=int, default=0)
    parser.add_argument("--outpaint-left", type=int, default=0)
    parser.add_argument("--outpaint-right", type=int, default=0)
    parser.add_argument("--model", default="runwayml/stable-diffusion-inpainting")
    parser.add_argument("--bg-removal-model", default="u2net")
    parser.add_argument("--storage-dir", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        source = fetch_image(engine, args.source_image_id, args.user_id)
        if source is None:
            raise ValueError(f"Source image {args.source_image_id} not found or not owned by this user.")
        source_path, _ = source

        if args.operation == "inpaint":
            if not args.mask_image_id:
                raise ValueError("inpaint requires --mask-image-id")
            mask = fetch_image(engine, args.mask_image_id, args.user_id)
            if mask is None:
                raise ValueError(f"Mask image {args.mask_image_id} not found or not owned by this user.")
            mask_path, _ = mask
            image = run_inpaint(args, source_path, mask_path)
        elif args.operation == "outpaint":
            image = run_outpaint(args, source_path)
        else:
            image = run_remove_background(args, source_path)

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        result_image_id = save_result_image(engine, args.user_id, args.storage_dir, buf.getvalue())

        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            result_image_id=result_image_id,
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Image editing dependencies not installed: {exc}. "
            "Run 'pip install -r imagegen/requirements.txt' (includes rembg for background "
            "removal) before starting an image edit job."
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
