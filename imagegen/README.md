# MyBuddy Image Generation

Runs as a **separate process** from the API, on purpose — a generation job can take a long
time on CPU-only hardware and must never be able to block or crash the main backend. The
backend launches this as a plain OS subprocess (`app/services/image_generation_service.py`)
and this script reports its own progress by writing directly to the `image_generation_jobs`
table via SQL, not by importing the backend. On success it also writes the generated PNG to
disk and records it as an `images` row — the same table/serving endpoint MyBuddy Vision
already built for chat image attachments (`GET /api/v1/images/{id}`), reused as-is here.

## Setup (only needed once, ideally on a GPU-equipped machine)

```bash
cd imagegen
python -m venv .venv
.venv\Scripts\activate      # Windows; source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

If `imagegen/.venv` doesn't exist, the backend falls back to its own Python interpreter to
launch this script — which will fail fast with a clear "install image generation
dependencies" message and mark the job `FAILED`, rather than silently doing nothing or
pretending to generate anything.

## What it does

1. Loads `IMAGE_GEN_MODEL` (default `stabilityai/sd-turbo`, a distilled Stable Diffusion
   variant built for 1-4 step inference) via `diffusers`.
2. Generates one image from the prompt (+ optional negative prompt, width/height, step
   count, seed).
3. Saves the PNG under the backend's own `storage_dir/images/<user-id>/` (the exact path
   convention `app/services/storage.py::save_image` uses) and inserts it into the `images`
   table directly via SQL, then points the job's `image_id` at it.

## Hardware reality check

This project's primary development machine has no GPU. `sd-turbo` is deliberately chosen
over a standard Stable Diffusion checkpoint because it needs only 1-4 inference steps
instead of 20-50, which is the difference between "slow" and "impractical" on CPU — but
expect generation to still take real time (well over a minute per image) without a GPU.
Set `IMAGE_GEN_MODEL` to a heavier/higher-quality checkpoint (e.g. a full SDXL model) on a
machine with an NVIDIA GPU.

## Generation parameters

`width`/`height`/`steps` are capped server-side (`IMAGE_GEN_MAX_WIDTH`/`_HEIGHT`/`_STEPS`)
so a request can't accidentally ask for something far slower than intended on CPU hardware.

## Manual invocation (for debugging, outside the API)

```bash
python scripts/generate.py \
  --job-id <existing-image-generation-job-uuid> \
  --user-id <user-uuid> \
  --prompt "a small red robot reading a book, watercolor style" \
  --width 512 --height 512 --steps 4 \
  --storage-dir ../backend/data \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```

## Image editing (`scripts/edit_image.py`)

A second script in this same venv — inpainting, outpainting, and background removal.
Reads its source image (and, for inpaint, a mask image) from the `images` table by id,
writes its result the same way `generate.py` does, and points the job's `result_image_id`
at it. `GET /api/v1/images/{id}` (built for Vision, reused by `generate.py` too) serves all
of it back with zero backend changes.

- **Mask convention** (inpaint): **white = regenerate this area, black = keep the original
  pixels** — the standard `diffusers` inpainting convention. The frontend's mask-painting
  canvas paints in white for exactly this reason.
- **Outpaint** needs no user-drawn mask: the script pads the canvas by the requested
  top/bottom/left/right amount, pastes the original image at the correct offset, and
  generates the white/black mask itself (white over the new padding, black over the
  original), then reuses the same inpainting pipeline.
- **Background removal** uses `rembg` (CPU-only `onnxruntime`, not the diffusion stack) —
  it downloads a small onnx model (`u2net` by default, `IMAGE_EDIT_BG_REMOVAL_MODEL`) to a
  local cache on first use. **This is comparatively fast even on CPU** — unlike inpaint/
  outpaint, which go through the same slow, non-distilled diffusion pipeline as any other
  Stable Diffusion inpainting checkpoint (`IMAGE_EDIT_MODEL`, default
  `runwayml/stable-diffusion-inpainting` — there's no turbo-distilled inpainting model as
  established as `sd-turbo` is for generation, so expect this to be noticeably slower than
  `scripts/generate.py`'s default text-to-image path).

```bash
python scripts/edit_image.py \
  --job-id <existing-image-edit-job-uuid> \
  --user-id <user-uuid> \
  --operation inpaint \
  --source-image-id <image-uuid> --mask-image-id <image-uuid> \
  --prompt "a red bicycle" --steps 20 \
  --storage-dir ../backend/data \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```
