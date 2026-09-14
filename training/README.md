# MyBuddy Fine-Tuning

Runs as a **separate process** from the API, on purpose — a training job can take hours and
must never be able to block or crash the main backend. The backend launches this as a plain
OS subprocess (`app/services/training_service.py`) and this script reports its own progress
by writing directly to the `training_jobs` table via SQL, not by importing the backend.

## Setup (only needed once, ideally on a GPU-equipped machine)

```bash
cd training
python -m venv .venv
.venv\Scripts\activate      # Windows; source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

If `training/.venv` doesn't exist, the backend falls back to its own Python interpreter to
launch this script — which will fail fast with a clear "install training dependencies"
message and mark the job `FAILED`, rather than silently doing nothing or pretending to train.

## What it does

1. Loads a JSONL instruction dataset (validated by the backend before a job can start — see
   `app/services/dataset_service.py` — each line is `{"messages": [{"role", "content"}, ...]}`).
2. Loads the specified base model (a Hugging Face model id) and tokenizer.
3. Wraps it with a LoRA adapter (`peft`) and trains via `trl`'s `SFTTrainer`.
4. Saves the resulting adapter to `--output-dir` and registers it in the `registered_models`
   table so it shows up via `GET /api/v1/models/registry`.

## Hardware reality check

This project's primary development machine has no GPU and 7GB RAM. LoRA fine-tuning even a
1B-parameter model is impractical there — this script will run, but expect it to be either
very slow or to run out of memory. Use a machine with an NVIDIA GPU (8GB+ VRAM comfortably
handles a 1B–3B model with LoRA) for anything beyond a smoke test.

## Dataset format

```json
{"messages": [{"role": "user", "content": "Explain photosynthesis."}, {"role": "assistant", "content": "Photosynthesis is..."}]}
```

One example per line. Validated on upload — a dataset must reach `VALIDATED` status before a
training job can be created against it.

## Manual invocation (for debugging, outside the API)

```bash
python scripts/train_lora.py \
  --job-id <existing-training-job-uuid> \
  --dataset ../backend/data/datasets/<user-id>/<file>.jsonl \
  --base-model meta-llama/Llama-3.2-1B \
  --output-dir ./output/test-run \
  --database-url postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy
```
