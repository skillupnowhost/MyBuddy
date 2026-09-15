import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import get_settings
from app.services.llm_provider import LLMProvider

settings = get_settings()


class OllamaProvider(LLMProvider):
    """LLMProvider implementation backed by a real local Ollama server (no mocking)."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=5.0) as client:
                resp = await client.get("/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def has_model(self, model: str) -> bool:
        models = await self.list_models()
        return any(m == model or m.startswith(f"{model}:") or m.split(":")[0] == model.split(":")[0] for m in models)

    async def pull_model(self, model: str) -> None:
        """Streams pull progress from Ollama and blocks until the model is fully downloaded."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            async with client.stream("POST", "/api/pull", json={"name": model, "stream": True}) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise RuntimeError(f"Failed to pull model {model}: {chunk['error']}")

    async def ensure_model(self, model: str) -> None:
        if not await self.has_model(model):
            await self.pull_model(model)

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        # 0.7 invites exactly the kind of hallucination that turned "pyramid" (a shape) into
        # the unrelated Pyramid web framework: a small local model has much less capacity to
        # recover from an early wrong turn than a frontier one, so the same "creative" setting
        # that's fine for a large cloud model reads as unreliable here. Lower and more
        # deterministic trades away creative variation for staying on-topic, which is the right
        # default for code and factual answers — callers that actually want variety (there are
        # none today) can still pass a higher value explicitly.
        temperature: float = 0.3,
        usage_sink: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """Yields assistant content deltas as they stream from the local model.

        If `usage_sink` is passed, it's filled in-place with real token/timing stats from
        Ollama's final chunk (prompt_eval_count, eval_count, total_duration_ns) once the
        stream completes — used for usage logging without changing the return type callers
        already depend on.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
            async with client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        if usage_sink is not None:
                            usage_sink["prompt_tokens"] = chunk.get("prompt_eval_count")
                            usage_sink["completion_tokens"] = chunk.get("eval_count")
                            usage_sink["duration_ms"] = (chunk.get("total_duration") or 0) // 1_000_000
                        break

    async def chat(self, model: str, messages: list[dict], temperature: float = 0.3) -> str:
        parts = [part async for part in self.chat_stream(model, messages, temperature)]
        return "".join(parts)


def get_llm_client() -> OllamaProvider:
    return OllamaProvider()
