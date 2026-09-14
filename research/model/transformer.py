"""A small, educational decoder-only transformer — the MyBuddy research model.

Deliberately not a reproduction of a production LLM (see spec §47): this exists so the
architecture is understandable end to end, not to be competitive. Every standard component
is here in a form you can read top to bottom: token embeddings, rotary positional embeddings
(RoPE), causal multi-head self-attention, RMSNorm, a SwiGLU feed-forward block, residual
connections, and an output head.

Default config ("nano") is intentionally tiny (~6M parameters) so it trains in seconds on
a CPU for smoke-testing the architecture itself. Scale up dim/n_layers/n_heads for anything
beyond that — see research/README.md for the size progression (nano -> 125M -> 350M -> 1B).
"""
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn


@dataclass
class MyBuddyConfig:
    vocab_size: int = 8000
    dim: int = 256
    n_layers: int = 6
    n_heads: int = 8
    max_seq_len: int = 512
    ffn_hidden_multiplier: float = 4.0
    rope_theta: float = 10000.0
    norm_eps: float = 1e-6

    @property
    def head_dim(self) -> int:
        return self.dim // self.n_heads


class RMSNorm(nn.Module):
    """Root-mean-square normalization — cheaper than LayerNorm (no mean-centering) and the
    standard choice in modern decoder-only transformers (LLaMA, Mistral, Qwen)."""

    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        norm = x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return norm * self.weight


def precompute_rope_freqs(head_dim: int, max_seq_len: int, theta: float) -> torch.Tensor:
    """Precomputes the complex rotation angles for RoPE, one set per position up to
    max_seq_len. Returned as complex numbers on the unit circle so applying the rotation is
    just a complex multiply (see apply_rope)."""
    freqs = 1.0 / (theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
    positions = torch.arange(max_seq_len).float()
    angles = torch.outer(positions, freqs)  # (max_seq_len, head_dim/2)
    return torch.polar(torch.ones_like(angles), angles)  # complex64, (max_seq_len, head_dim/2)


def apply_rope(x: torch.Tensor, freqs_cis: torch.Tensor) -> torch.Tensor:
    """Rotates query/key vectors by position-dependent angles — this is how RoPE injects
    positional information directly into attention scores instead of adding a positional
    embedding to the input. x: (batch, seq, heads, head_dim)."""
    x_complex = torch.view_as_complex(x.float().reshape(*x.shape[:-1], -1, 2))
    freqs_cis = freqs_cis[: x.shape[1]].unsqueeze(0).unsqueeze(2)  # (1, seq, 1, head_dim/2)
    x_rotated = x_complex * freqs_cis
    return torch.view_as_real(x_rotated).flatten(-2).type_as(x)


class CausalSelfAttention(nn.Module):
    def __init__(self, config: MyBuddyConfig):
        super().__init__()
        self.n_heads = config.n_heads
        self.head_dim = config.head_dim
        self.wq = nn.Linear(config.dim, config.dim, bias=False)
        self.wk = nn.Linear(config.dim, config.dim, bias=False)
        self.wv = nn.Linear(config.dim, config.dim, bias=False)
        self.wo = nn.Linear(config.dim, config.dim, bias=False)

    def forward(self, x: torch.Tensor, freqs_cis: torch.Tensor, causal_mask: torch.Tensor) -> torch.Tensor:
        batch, seq, dim = x.shape

        q = self.wq(x).view(batch, seq, self.n_heads, self.head_dim)
        k = self.wk(x).view(batch, seq, self.n_heads, self.head_dim)
        v = self.wv(x).view(batch, seq, self.n_heads, self.head_dim)

        q = apply_rope(q, freqs_cis)
        k = apply_rope(k, freqs_cis)

        q, k, v = (t.transpose(1, 2) for t in (q, k, v))  # (batch, heads, seq, head_dim)

        scores = (q @ k.transpose(-2, -1)) / (self.head_dim**0.5)
        scores = scores + causal_mask  # additive -inf mask above the diagonal
        attn = F.softmax(scores, dim=-1)
        out = attn @ v  # (batch, heads, seq, head_dim)

        out = out.transpose(1, 2).contiguous().view(batch, seq, dim)
        return self.wo(out)


class SwiGLUFeedForward(nn.Module):
    """SwiGLU gated feed-forward — the modern replacement for a plain ReLU/GELU MLP,
    used in LLaMA/PaLM-family models. Gate and value projections run in parallel; the SiLU
    (Swish) activation gates how much of the value projection passes through."""

    def __init__(self, dim: int, hidden_multiplier: float):
        super().__init__()
        hidden_dim = int(dim * hidden_multiplier)
        self.w_gate = nn.Linear(dim, hidden_dim, bias=False)
        self.w_value = nn.Linear(dim, hidden_dim, bias=False)
        self.w_out = nn.Linear(hidden_dim, dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w_out(F.silu(self.w_gate(x)) * self.w_value(x))


class TransformerBlock(nn.Module):
    """Pre-norm residual block: norm -> attention -> residual add, then norm -> feed-forward
    -> residual add. Pre-norm (vs. the original post-norm) is what makes deep transformers
    trainable without careful learning-rate warmup tuning."""

    def __init__(self, config: MyBuddyConfig):
        super().__init__()
        self.attn_norm = RMSNorm(config.dim, config.norm_eps)
        self.attn = CausalSelfAttention(config)
        self.ffn_norm = RMSNorm(config.dim, config.norm_eps)
        self.ffn = SwiGLUFeedForward(config.dim, config.ffn_hidden_multiplier)

    def forward(self, x: torch.Tensor, freqs_cis: torch.Tensor, causal_mask: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.attn_norm(x), freqs_cis, causal_mask)
        x = x + self.ffn(self.ffn_norm(x))
        return x


class MyBuddyTransformer(nn.Module):
    def __init__(self, config: MyBuddyConfig):
        super().__init__()
        self.config = config
        self.tok_embeddings = nn.Embedding(config.vocab_size, config.dim)
        self.layers = nn.ModuleList(TransformerBlock(config) for _ in range(config.n_layers))
        self.final_norm = RMSNorm(config.dim, config.norm_eps)
        self.output_head = nn.Linear(config.dim, config.vocab_size, bias=False)

        # Precomputed once for the model's max context length; sliced per forward pass.
        self.register_buffer(
            "freqs_cis", precompute_rope_freqs(config.head_dim, config.max_seq_len, config.rope_theta), persistent=False
        )

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(self, tokens: torch.Tensor, targets: torch.Tensor | None = None):
        batch, seq = tokens.shape
        if seq > self.config.max_seq_len:
            raise ValueError(f"Sequence length {seq} exceeds max_seq_len {self.config.max_seq_len}")

        x = self.tok_embeddings(tokens)
        freqs_cis = self.freqs_cis[:seq].to(x.device)

        causal_mask = torch.full((seq, seq), float("-inf"), device=x.device).triu(diagonal=1)

        for layer in self.layers:
            x = layer(x, freqs_cis, causal_mask)

        x = self.final_norm(x)
        logits = self.output_head(x)

        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100)

        return logits, loss

    @torch.no_grad()
    def generate(self, tokens: torch.Tensor, max_new_tokens: int, temperature: float = 1.0) -> torch.Tensor:
        """Greedy/temperature sampling, one token at a time — simple and correct, not
        optimized (no KV cache). Fine for verifying the model works; a real serving path
        would cache past key/value projections instead of recomputing the full sequence
        every step."""
        for _ in range(max_new_tokens):
            context = tokens[:, -self.config.max_seq_len :]
            logits, _ = self.forward(context)
            next_logits = logits[:, -1, :] / max(temperature, 1e-6)
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            tokens = torch.cat([tokens, next_token], dim=1)
        return tokens
