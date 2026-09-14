from collections.abc import AsyncGenerator

from app.services.llm_provider import LLMProvider


class MockProvider(LLMProvider):
    """Deterministic in-memory LLMProvider used by tests. Never used in real request paths."""

    def __init__(self, reply: str = "Hello there!", models: list[str] | None = None, replies: list[str] | None = None):
        self.reply = reply
        self.models = models or ["mock-model"]
        self.last_model: str | None = None
        # Optional: return a different canned reply on each successive call (e.g. to test a
        # retry loop where the first response is deliberately invalid). Once exhausted, the
        # last entry repeats. `reply` is used as-is when `replies` isn't given.
        self.replies = replies
        self.call_count = 0

    def _next_reply(self) -> str:
        if not self.replies:
            return self.reply
        index = min(self.call_count, len(self.replies) - 1)
        return self.replies[index]

    async def chat_stream(
        self, model: str, messages: list[dict], temperature: float = 0.7, usage_sink: dict | None = None
    ) -> AsyncGenerator[str, None]:
        self.last_model = model
        reply = self._next_reply()
        self.call_count += 1
        chunk_size = 5
        for i in range(0, len(reply), chunk_size):
            yield reply[i : i + chunk_size]
        if usage_sink is not None:
            usage_sink["prompt_tokens"] = 10
            usage_sink["completion_tokens"] = len(reply.split())
            usage_sink["duration_ms"] = 1

    async def chat(self, model: str, messages: list[dict], temperature: float = 0.7) -> str:
        self.last_model = model
        reply = self._next_reply()
        self.call_count += 1
        return reply

    async def list_models(self) -> list[str]:
        return self.models

    async def health(self) -> bool:
        return True
