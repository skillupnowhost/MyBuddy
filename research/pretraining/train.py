#!/usr/bin/env python
"""Pretraining loop for the MyBuddy research model (see research/model/transformer.py).

This is intentionally a plain, readable training loop, not a distributed/mixed-precision
production pipeline — the point of this research track (spec §45-47) is an understandable
reference implementation, not throughput. Scaling up is a matter of swapping in a bigger
MyBuddyConfig, a real (large, deduplicated, licensed) corpus, and actual distributed training
infrastructure — none of which this script pretends to provide.

Usage:
    python train.py --corpus ../data/corpus.txt --tokenizer ../tokenizer/mybuddy-tokenizer.json \
                     --steps 200 --batch-size 8 --seq-len 128 --checkpoint-dir ./checkpoints
"""
import argparse
import os
import sys

import torch
from tokenizers import Tokenizer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from model.transformer import MyBuddyConfig, MyBuddyTransformer  # noqa: E402


def load_corpus_ids(corpus_path: str, tokenizer: Tokenizer) -> torch.Tensor:
    with open(corpus_path, encoding="utf-8") as f:
        text = f.read()
    ids = tokenizer.encode(text).ids
    if len(ids) < 2:
        raise ValueError("Corpus is too small to train on — need at least a couple of tokens.")
    return torch.tensor(ids, dtype=torch.long)


def get_batch(data: torch.Tensor, batch_size: int, seq_len: int, device: str) -> tuple[torch.Tensor, torch.Tensor]:
    """Samples random contiguous windows from the corpus. targets are inputs shifted by one
    position — standard next-token-prediction pretraining."""
    max_start = len(data) - seq_len - 1
    if max_start <= 0:
        raise ValueError(f"Corpus has {len(data)} tokens, too short for seq_len={seq_len}")
    starts = torch.randint(0, max_start, (batch_size,))
    x = torch.stack([data[s : s + seq_len] for s in starts]).to(device)
    y = torch.stack([data[s + 1 : s + seq_len + 1] for s in starts]).to(device)
    return x, y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--checkpoint-dir", default="./checkpoints")
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument(
        "--size",
        default="nano",
        choices=["nano", "125m", "350m", "1b"],
        help="Model size preset — see research/README.md for the parameter counts these map to.",
    )
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = Tokenizer.from_file(args.tokenizer)
    data = load_corpus_ids(args.corpus, tokenizer)

    config = _size_presets()[args.size]
    config.vocab_size = tokenizer.get_vocab_size()
    model = MyBuddyTransformer(config).to(device)
    print(f"MyBuddy-{args.size}: {model.num_parameters():,} parameters, device={device}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    os.makedirs(args.checkpoint_dir, exist_ok=True)

    model.train()
    for step in range(1, args.steps + 1):
        x, y = get_batch(data, args.batch_size, args.seq_len, device)
        _, loss = model(x, targets=y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if step % args.log_every == 0 or step == 1:
            print(f"step {step}/{args.steps}  loss {loss.item():.4f}")

    checkpoint_path = os.path.join(args.checkpoint_dir, "mybuddy-nano-final.pt")
    torch.save({"config": config, "model_state_dict": model.state_dict()}, checkpoint_path)
    print(f"Saved checkpoint to {checkpoint_path}")


def _size_presets() -> dict[str, MyBuddyConfig]:
    """Parameter-count progression per spec §45 — start tiny, only grow once the pipeline
    and dataset actually justify it. Figures are approximate and vocab-size-dependent."""
    return {
        "nano": MyBuddyConfig(dim=256, n_layers=6, n_heads=8, max_seq_len=512),  # ~6M params
        "125m": MyBuddyConfig(dim=768, n_layers=12, n_heads=12, max_seq_len=1024),
        "350m": MyBuddyConfig(dim=1024, n_layers=24, n_heads=16, max_seq_len=1024),
        "1b": MyBuddyConfig(dim=2048, n_layers=24, n_heads=16, max_seq_len=2048),
    }


if __name__ == "__main__":
    main()
