from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings

settings = get_settings()


class EmbeddingProvider(ABC):
    """Abstraction over an embedding backend, mirroring LLMProvider. Swapping the embedding
    model/engine (e.g. a hosted embedding API, or a future MyBuddy embedding model) means
    adding one implementation here — RAG code never talks to an embedding API directly."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            resp = await client.post("/api/embed", json={"model": self.model, "input": texts})
            resp.raise_for_status()
            data = resp.json()
            return data["embeddings"]


def get_embedding_provider() -> EmbeddingProvider:
    return OllamaEmbeddingProvider()
