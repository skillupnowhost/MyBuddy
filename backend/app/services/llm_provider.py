from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class LLMProvider(ABC):
    """Abstraction over a local/self-hosted inference backend.

    The rest of the backend talks only to this interface, never to a specific
    engine's HTTP API directly. Swapping Ollama for vLLM, llama.cpp, or a future
    MyBuddy-trained model server means adding a new implementation here — no
    changes to routers, services, or schemas.
    """

    @abstractmethod
    async def chat_stream(
        self, model: str, messages: list[dict], temperature: float = 0.7, usage_sink: dict | None = None
    ) -> AsyncGenerator[str, None]:
        """Yield assistant content deltas as they are generated. If `usage_sink` is given,
        implementations that can report real token/timing stats fill it in-place once the
        stream completes; implementations that can't simply leave it untouched."""
        raise NotImplementedError
        yield  # pragma: no cover - makes this an async generator for type-checkers

    @abstractmethod
    async def chat(self, model: str, messages: list[dict], temperature: float = 0.7) -> str:
        """Return the full assistant reply (non-streaming)."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List models currently available to the inference backend."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the inference backend is reachable and ready."""
        ...
