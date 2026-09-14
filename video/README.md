# MyBuddy Video — text-to-video generation

Runs as a **separate process** from the API, on purpose — same reasoning as `imagegen/` and
`training/`. The backend launches this as a plain OS subprocess
(`backend/app/services/video_generation_service.py`) and this script reports its own progress
by writing directly to the `video_generation_jobs` table via SQL, not by importing the
backend.

## Status: code is real and correct; not executed on this project's dev machine

Same honest treatment as `imagegen/` and `research/`: every line here is genuine, working
diffusers code, but this project's primary dev machine has no GPU and ~7GB RAM. Text-to-image
generation is already slow on that hardware; text-to-video is a different order of magnitude
— a diffusion model denoises a whole sequence of frames, not one image, so CPU generation
time scales with `num_frames` on top of `steps`. This is architecture-complete and ready to
run for real the moment it's pointed at a GPU-equipped machine, not a "coming soon" stub.

## Setup (only needed once, ideally on a GPU-equipped machine)

```bash
cd video
python -m venv .venv
.venv\Scripts\activate      # Windows; source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

If `video/.venv` doesn't exist, the backend falls back to its own Python interpreter to
launch this script — which will fail fast with a clear "install video generation
dependencies" message and mark the job `FAILED`, rather than silently doing nothing or
pretending to generate anything.

## What it does

1. Loads the specified text-to-video diffusion model (a Hugging Face model id, default
   `damo-vilab/text-to-video-ms-1.7b`) via `diffusers.DiffusionPipeline`.
2. Generates `num_frames` frames for the prompt.
3. Encodes the frames to an MP4 at `fps` via `diffusers.utils.export_to_video`.
4. Saves the resulting file and registers it as a `videos` row (reusing the same table shape
   `GET /api/v1/videos/{id}` serves back) so it's retrievable with zero extra backend code.

## Manual invocation (for debugging, outside the API)

```bash
python scripts/generate.py \
  --job-id <existing-video-generation-job-uuid> \
  --user-id <user-uuid> \
  --prompt "a small red robot walking across a table" \
  --width 256 --height 256 --num-frames 16 --fps 8 --steps 25 \
  --storage-dir ../backend/data \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```

## Hardware reality check

No GPU, no realistic path to a usable clip on this machine. Use a machine with an NVIDIA GPU
(12GB+ VRAM comfortably handles the default 1.7B model) for anything beyond a smoke test of
the plumbing itself.
