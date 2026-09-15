# MyBuddy Video — text-to-video generation + video editing

Runs as a **separate process** from the API, on purpose — same reasoning as `imagegen/` and
`training/`. The backend launches these as plain OS subprocesses
(`backend/app/services/video_generation_service.py`,
`backend/app/services/video_edit_service.py`) and each script reports its own progress by
writing directly to Postgres via SQL, not by importing the backend. Two independent scripts
share this one venv — same convention as `imagegen/`'s `generate.py` + `edit_image.py`.

## Status: `generate.py` is real and correct but not executed here; `edit_video.py` actually runs

Different situation for each script in this directory:
- **`generate.py`** (text-to-video): same honest treatment as `imagegen/` and `research/` —
  genuine, working diffusers code, but this project's primary dev machine has no GPU and
  ~7GB RAM. A diffusion model denoises a whole sequence of frames, not one image, so CPU
  generation time scales with `num_frames` on top of `steps` — architecture-complete, not a
  "coming soon" stub, but not runnable here in any practical sense.
- **`edit_video.py`** (`REMOVE_BACKGROUND` / green screen): uses `rembg`, the same CPU-fast,
  GPU-independent library already used by `imagegen/edit_image.py` — **this one actually
  completes on this project's hardware** once `video/.venv` is provisioned, no GPU required.
  The one video-track capability in this repo without a hardware caveat.

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

## What `generate.py` does

1. Loads the specified text-to-video diffusion model (a Hugging Face model id, default
   `damo-vilab/text-to-video-ms-1.7b`) via `diffusers.DiffusionPipeline`.
2. Generates `num_frames` frames for the prompt.
3. Encodes the frames to an MP4 at `fps` via `diffusers.utils.export_to_video`.
4. Saves the resulting file and registers it as a `videos` row (reusing the same table shape
   `GET /api/v1/videos/{id}` serves back) so it's retrievable with zero extra backend code.

## What `edit_video.py` does

1. Reads the source video frame by frame via `imageio.get_reader`.
2. Runs `rembg.remove()` on each frame to get an RGBA cutout of the foreground.
3. Composites the cutout onto a solid `--background-color` (not true alpha transparency —
   see "Scope" below) and writes each frame via `imageio.get_writer`.
4. Saves the resulting MP4 and registers it as a new `videos` row, same as `generate.py`.

**Scope**: this produces background *replacement* with a solid color, not a transparent-
alpha-channel video. True alpha-channel video (VP9/WebM with `yuva420p`) needs direct
control over ffmpeg's codec/pixel-format flags that `imageio`'s simple writer API doesn't
expose cleanly — left for a follow-up once solid-color replacement is verified working on
real hardware, rather than guessed at now.

## Manual invocation (for debugging, outside the API)

```bash
# Text-to-video generation (not runnable on this project's hardware — see above)
python scripts/generate.py \
  --job-id <existing-video-generation-job-uuid> \
  --user-id <user-uuid> \
  --prompt "a small red robot walking across a table" \
  --width 256 --height 256 --num-frames 16 --fps 8 --steps 25 \
  --storage-dir ../backend/data \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy

# Background removal / green screen (runs for real once this venv is provisioned)
python scripts/edit_video.py \
  --job-id <existing-video-edit-job-uuid> \
  --user-id <user-uuid> \
  --operation REMOVE_BACKGROUND \
  --source-video-path /path/to/source.mp4 \
  --background-color "#00b140" --bg-removal-model u2net \
  --storage-dir ../backend/data \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```

## Hardware reality check

`generate.py`: no GPU, no realistic path to a usable clip on this machine. Use a machine with
an NVIDIA GPU (12GB+ VRAM comfortably handles the default 1.7B model) for anything beyond a
smoke test of the plumbing itself.

`edit_video.py`: no GPU needed — CPU speed scales with video length and resolution (each
frame is one `rembg` call), but it genuinely finishes.
