#!/usr/bin/env python
"""Standalone LoRA fine-tuning job runner.

Deliberately independent of the backend's `app` package — this is meant to be a separately
deployable unit (see training/README.md), possibly on a different, GPU-equipped machine than
the one running the API. It talks to Postgres only to report its own status, via plain SQL,
not the backend's ORM models.

Usage:
    python train_lora.py --job-id <uuid> --dataset <path.jsonl> --base-model <hf-model-id>
                          --output-dir <dir> --database-url <postgresql+psycopg://...>
"""
import argparse
import json
import sys
import traceback
from datetime import datetime, timezone

from sqlalchemy import create_engine, text


def update_job(engine, job_id: str, **fields) -> None:
    # eval_metrics is a JSON column; a plain string bind param needs an explicit cast or
    # Postgres rejects it as "column is of type json but expression is of type text".
    set_clause = ", ".join(
        f"{key} = CAST(:{key} AS JSON)" if key == "eval_metrics" else f"{key} = :{key}" for key in fields
    )
    fields["job_id"] = job_id
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE training_jobs SET {set_clause} WHERE id = CAST(:job_id AS uuid)"), fields)


def register_model(engine, name: str, base_model: str, capability: str, training_job_id: str, location: str) -> None:
    """Every completed training run is auto-registered as EXPERIMENTAL (spec §13) — it must
    pass evaluation (see evaluate_model.py) before an admin can promote it toward PRODUCTION."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO registered_models (id, name, version, base_model, capability, training_job_id, "
                "quantization, location, status, created_at) "
                "VALUES (gen_random_uuid(), :name, 'v1', :base_model, :capability, CAST(:job_id AS uuid), "
                "NULL, :location, 'EXPERIMENTAL', now())"
            ),
            {
                "name": name,
                "base_model": base_model,
                "capability": capability,
                "job_id": training_job_id,
                "location": location,
            },
        )


def load_dataset_examples(dataset_path: str) -> list[dict]:
    examples = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def run_training(args, engine) -> tuple[str, dict]:
    """Real LoRA fine-tuning via the standard HF ecosystem. Only reached if torch/transformers/
    peft/trl/datasets/accelerate are actually installed (see training/requirements.txt) — on
    this project's primary dev machine (no GPU, 7GB RAM) that import deliberately fails, and
    the caller reports that clearly rather than pretending to train anything."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    examples = load_dataset_examples(args.dataset)

    # Hold out a small validation slice so the job reports a real eval_loss (spec §12: every
    # newly trained model must be tested), not just training loss. With very small datasets
    # (smoke tests, early users) there may be nothing left to hold out — that's fine, we just
    # skip eval rather than starving training of its only examples.
    n_eval = max(1, len(examples) // 10) if len(examples) >= 10 else 0
    train_examples = examples[: len(examples) - n_eval] if n_eval else examples
    eval_examples = examples[len(examples) - n_eval :] if n_eval else None

    train_dataset = Dataset.from_list(train_examples)
    eval_dataset = Dataset.from_list(eval_examples) if eval_examples else None

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float32 if not torch.cuda.is_available() else torch.bfloat16,
    )

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_dataset is not None else "no",
        report_to=[],
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
    )
    train_result = trainer.train()
    trainer.save_model(args.output_dir)

    metrics = {"train_loss": train_result.metrics.get("train_loss")}
    if eval_dataset is not None:
        metrics["eval_loss"] = trainer.evaluate().get("eval_loss")

    return args.output_dir, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--capability", default="TEXT", choices=["TEXT", "CODE"])
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    update_job(engine, args.job_id, status="RUNNING")

    try:
        output_path, metrics = run_training(args, engine)
        register_model(
            engine,
            name=f"mybuddy-finetune-{args.job_id[:8]}",
            base_model=args.base_model,
            capability=args.capability,
            training_job_id=args.job_id,
            location=output_path,
        )
        update_job(
            engine,
            args.job_id,
            status="COMPLETED",
            output_path=output_path,
            eval_metrics=json.dumps(metrics),
            completed_at=datetime.now(timezone.utc),
        )
        return 0
    except ImportError as exc:
        message = (
            f"Training dependencies not installed: {exc}. "
            "Run 'pip install -r training/requirements.txt' (ideally on a GPU-equipped "
            "machine) before starting a training job."
        )
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - any training failure must be reported, not raised into the void
        message = f"{exc}\n{traceback.format_exc()}"[:4000]
        update_job(engine, args.job_id, status="FAILED", error_message=message, completed_at=datetime.now(timezone.utc))
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
