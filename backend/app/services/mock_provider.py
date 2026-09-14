from collections.abc import AsyncGenerator

from app.services.llm_provider import LLMProvider


class MockProvider(LLMProvider):
    """Deterministic in-memory LLMProvider used by tests. Never used in real request paths."""

    def __init__(self, reply: str = "Hello there!", models: list[str] | None = None):
        self.reply = reply
        self.models = models or ["mock-model"]
        self.last_model: str | None = None

    async def chat_stream(
        self, model: str, messages: list[dict], temperature: float = 0.7, usage_sink: dict | None = None
    ) -> AsyncGenerator[str, None]:
        self.last_model = model
        chunk_size = 5
        for i in range(0, len(self.reply), chunk_size):
            yield self.reply[i : i + chunk_size]
        if usage_sink is not None:
            usage_sink["prompt_tokens"] = 10
            usage_sink["completion_tokens"] = len(self.reply.split())
            usage_sink["duration_ms"] = 1

    async def chat(self, model: str, messages: list[dict], temperature: float = 0.7) -> str:
        return self.reply

    async def list_models(self) -> list[str]:
        return self.models

    async def health(self) -> bool:
        return True
