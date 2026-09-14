# MyBuddy Research Track — Custom Model From Scratch

Phase 6 of the roadmap. This is an **educational reference implementation**, not a
production pretraining pipeline — the goal is a transformer you can read top to bottom and
understand, matching spec §47's explicit instruction not to attempt reproducing a massive
production LLM here. It is entirely separate from `training/` (which fine-tunes existing
Hugging Face models via LoRA); this directory trains a MyBuddy-native architecture from
random initialization.

## Status: code is real and correct; not executed on this project's dev machine

Every file here is genuine, runnable PyTorch code — verified with `python -m py_compile`
(syntax-checked) — but **not executed live** in this project's environment: the primary dev
machine has ~7GB RAM with ~1GB free at the time of writing (Postgres, Ollama, and the backend
are all resident), and installing torch plus running even a tiny training loop risked
destabilizing those live services. Rather than skip verification or claim success without
evidence, this README says so plainly. Run it yourself on a machine with headroom (or a GPU)
using the steps below — nothing here is fake, it just hasn't been smoke-tested in this
particular session.

## Pipeline (per spec §45-47)

1. **Dataset** — collect, clean, deduplicate, filter for quality (not implemented here;
   `data/corpus.sample.txt` is a 3-paragraph placeholder to exercise the pipeline, nothing more).
2. **Tokenizer** — `tokenizer/train_tokenizer.py` trains a byte-level BPE tokenizer via
   Hugging Face `tokenizers`.
3. **Architecture** — `model/transformer.py`: token embeddings, rotary positional embeddings
   (RoPE), causal multi-head self-attention, RMSNorm, a SwiGLU feed-forward block, residual
   connections, and an output head — the standard modern decoder-only transformer, written
   for readability over performance (no KV cache, no flash-attention kernel).
4. **Pretraining** — `pretraining/train.py`: a plain next-token-prediction training loop with
   four size presets (`nano` ~6M params for smoke-testing, up through `125m`/`350m`/`1b`,
   per spec §45's "only grow once the pipeline and dataset justify it").
5. **Evaluation, instruction tuning, preference tuning, quantization, serving** — not built
   yet. These are the natural next steps once a base model actually exists; there's nothing
   to evaluate or instruction-tune before step 4 has run on a real corpus.

## Setup

```bash
cd research
python -m venv .venv
.venv\Scripts\activate      # Windows; source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
```

## Running the smoke test yourself

```bash
python tokenizer/train_tokenizer.py --corpus data/corpus.sample.txt --vocab-size 500 --out tokenizer/mybuddy-tokenizer.json
python pretraining/train.py --corpus data/corpus.sample.txt --tokenizer tokenizer/mybuddy-tokenizer.json --size nano --steps 50 --batch-size 4 --seq-len 32
```

Expected: the tokenizer trains in under a second (tiny corpus); the `nano` model
(~6M parameters) initializes, and training loss should visibly decrease over 50 steps as it
memorizes the tiny sample corpus (with a corpus this small and repetitive, that's expected
and fine — it's testing the mechanics, not producing a useful model). A checkpoint is saved
to `pretraining/checkpoints/mybuddy-nano-final.pt`.

## Hardware reality check

Same as `training/README.md`: this machine has no GPU and 7GB RAM. The `nano` preset should
run on CPU. Anything from `125m` up needs real compute — a GPU, and hours-to-days of training
time on an actual (large, licensed, deduplicated) corpus, not the 3-paragraph placeholder here.

## Licensing note

Any real corpus you train on must respect the license/provenance of its source data (spec
§62-63) — this scaffold takes no position on where you'd source such a corpus, and ships only
a synthetic placeholder written for this project.
