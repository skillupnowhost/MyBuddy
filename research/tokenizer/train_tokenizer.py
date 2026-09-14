#!/usr/bin/env python
"""Trains a byte-level BPE tokenizer for the MyBuddy research model.

Usage:
    python train_tokenizer.py --corpus ../data/corpus.txt --vocab-size 8000 --out ./mybuddy-tokenizer.json

This is Phase 6, step 1 of the roadmap in research/README.md: dataset -> tokenizer ->
architecture -> pretraining -> evaluation -> instruction tuning. A small vocab size (8000)
is deliberate — this is a research/educational scaffold, not a production tokenizer trained
on hundreds of gigabytes of deduplicated web text.
"""
import argparse

from tokenizers import ByteLevelBPETokenizer


def train(corpus_path: str, vocab_size: int, out_path: str) -> None:
    tokenizer = ByteLevelBPETokenizer()
    tokenizer.train(
        files=[corpus_path],
        vocab_size=vocab_size,
        min_frequency=2,
        special_tokens=["<pad>", "<bos>", "<eos>", "<unk>"],
    )
    tokenizer.save(out_path)
    print(f"Saved tokenizer ({tokenizer.get_vocab_size()} tokens) to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, help="Path to a plain-text training corpus")
    parser.add_argument("--vocab-size", type=int, default=8000)
    parser.add_argument("--out", default="./mybuddy-tokenizer.json")
    args = parser.parse_args()
    train(args.corpus, args.vocab_size, args.out)


if __name__ == "__main__":
    main()
