# MyBuddy CG — text/image to 3D mesh generation

Runs as a **separate process** from the API, on purpose — same reasoning as `imagegen/` and
`video/`. The backend launches this as a plain OS subprocess
(`backend/app/services/model_3d_generation_service.py`) and this script reports its own
progress by writing directly to the `model_3d_generation_jobs` table via SQL, not by
importing the backend.

## Status: code is real and correct; not executed on this project's dev machine

Same honest treatment as every other generation subprocess in this repo. Uses OpenAI's
Shap-E model via `diffusers` — the same library already used for Image and Video, rather than
introducing a new ML stack for 3D. `ShapEPipeline` handles text-to-3D; `ShapEImg2ImgPipeline`
handles image-to-3D. Both denoise a latent 3D representation and export it as a mesh.

## Setup (only needed once, ideally on a GPU-equipped machine)

```bash
cd cg3d
python -m venv .venv
.venv\Scripts\activate      # Windows; source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

If `cg3d/.venv` doesn't exist, the backend falls back to its own Python interpreter to launch
this script — which will fail fast with a clear "install 3D generation dependencies" message
and mark the job `FAILED`, rather than silently doing nothing.

## What it does

1. Loads `ShapEPipeline` (text prompt given) or `ShapEImg2ImgPipeline` (source image given)
   from Hugging Face.
2. Generates a mesh (`output_type="mesh"`).
3. Exports it to Wavefront OBJ via `diffusers.utils.export_to_obj`.
4. Saves the file and registers it as a `models_3d` row (`GET /api/v1/models3d/{id}` serves
   it back).

## Export formats

v1 produces **OBJ only**. The spec's fuller export list (FBX, GLB, GLTF, USD, USDZ, PLY, STL)
is not implemented — OBJ is what `diffusers.utils.export_to_obj` produces directly with no
extra conversion library; the others would need a real mesh-format conversion step (e.g. via
`trimesh` or Blender's Python API) that hasn't been built. Add format conversion as its own
follow-up once OBJ generation is actually verified working on real hardware, not before.

## Manual invocation (for debugging, outside the API)

```bash
# Text-to-3D
python scripts/generate.py --job-id <uuid> --user-id <uuid> \
  --prompt "a low-poly red sports car" --steps 64 --guidance-scale 15.0 \
  --storage-dir ../backend/data --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy

# Image-to-3D
python scripts/generate.py --job-id <uuid> --user-id <uuid> \
  --source-image-path /path/to/image.png --steps 64 --guidance-scale 3.0 \
  --storage-dir ../backend/data --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```

## Hardware reality check

No GPU, no realistic path to a usable mesh on this machine in reasonable time. Use a machine
with an NVIDIA GPU for anything beyond a smoke test of the plumbing itself.
