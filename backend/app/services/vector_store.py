import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk


@dataclass
class VectorMatch:
    chunk_id: str
    score: float


class VectorStoreProvider(ABC):
    """Abstraction over similarity search. Swapping this implementation for Qdrant (or
    anything else, at a scale where brute-force search stops being appropriate) means
    adding one implementation here — RAG code never computes similarity directly."""

    @abstractmethod
    def add(self, db: Session, chunk_embeddings: dict[str, list[float]]) -> None:
        ...

    @abstractmethod
    def query(self, db: Session, user_id: str, embedding: list[float], top_k: int) -> list[VectorMatch]:
        ...

    @abstractmethod
    def delete(self, db: Session, chunk_ids: list[str]) -> None:
        ...


class PostgresVectorStoreProvider(VectorStoreProvider):
    """Stores each chunk's embedding directly on its row (DocumentChunk.embedding, a JSON
    float array) and does brute-force cosine similarity in Python at query time.

    No separate vector database, no native-compiled ANN library — appropriate for a single
    self-hosted user's document count (thousands of chunks, not millions). Swap in a real
    ANN-backed provider (Qdrant, pgvector+ivfflat) if that ever stops being true.
    """

    def add(self, db: Session, chunk_embeddings: dict[str, list[float]]) -> None:
        for chunk_id, embedding in chunk_embeddings.items():
            row = db.get(DocumentChunk, uuid.UUID(chunk_id))
            if row is not None:
                row.embedding = embedding
        db.commit()

    def query(self, db: Session, user_id: str, embedding: list[float], top_k: int) -> list[VectorMatch]:
        rows = (
            db.query(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.user_id == uuid.UUID(user_id), DocumentChunk.embedding.isnot(None))
            .all()
        )
        if not rows:
            return []

        query_vec = np.array(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec) or 1.0

        scored = []
        for row in rows:
            vec = np.array(row.embedding, dtype=np.float32)
            denom = (np.linalg.norm(vec) or 1.0) * query_norm
            score = float(np.dot(vec, query_vec) / denom)
            scored.append((score, row.id))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [VectorMatch(chunk_id=str(chunk_id), score=score) for score, chunk_id in scored[:top_k]]

    def delete(self, db: Session, chunk_ids: list[str]) -> None:
        # Rows (and their embeddings) are removed via cascade delete when their Document is
        # deleted — nothing extra to do for this implementation.
        pass


def get_vector_store() -> VectorStoreProvider:
    return PostgresVectorStoreProvider()
