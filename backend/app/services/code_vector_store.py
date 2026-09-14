import uuid
from abc import ABC, abstractmethod

import numpy as np
from sqlalchemy.orm import Session

from app.db.models.code_chunk import CodeChunk
from app.db.models.code_file import CodeFile
from app.db.models.code_project import CodeProject
from app.services.vector_store import VectorMatch


class CodeVectorStoreProvider(ABC):
    """Mirrors VectorStoreProvider, scoped to code chunks. Kept as a separate abstraction
    rather than generalizing VectorStoreProvider because a code chunk's ownership chain
    (CodeChunk -> CodeFile -> CodeProject.user_id) is a different join than documents', and
    code RAG is additionally scoped to one open project, not "all of the user's content"."""

    @abstractmethod
    def add(self, db: Session, chunk_embeddings: dict[str, list[float]]) -> None:
        ...

    @abstractmethod
    def query(
        self, db: Session, user_id: str, embedding: list[float], top_k: int, project_id: str
    ) -> list[VectorMatch]:
        ...

    @abstractmethod
    def delete(self, db: Session, chunk_ids: list[str]) -> None:
        ...


class PostgresCodeVectorStoreProvider(CodeVectorStoreProvider):
    """Same brute-force cosine-similarity approach as PostgresVectorStoreProvider — see
    that class's docstring for the scale rationale."""

    def add(self, db: Session, chunk_embeddings: dict[str, list[float]]) -> None:
        for chunk_id, embedding in chunk_embeddings.items():
            row = db.get(CodeChunk, uuid.UUID(chunk_id))
            if row is not None:
                row.embedding = embedding
        db.commit()

    def query(
        self, db: Session, user_id: str, embedding: list[float], top_k: int, project_id: str
    ) -> list[VectorMatch]:
        rows = (
            db.query(CodeChunk)
            .join(CodeFile, CodeChunk.file_id == CodeFile.id)
            .join(CodeProject, CodeFile.project_id == CodeProject.id)
            .filter(
                CodeProject.user_id == uuid.UUID(user_id),
                CodeProject.id == uuid.UUID(project_id),
                CodeChunk.embedding.isnot(None),
            )
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
        # Rows (and their embeddings) are removed via cascade delete when their CodeProject
        # is deleted — nothing extra to do for this implementation.
        pass


def get_code_vector_store() -> CodeVectorStoreProvider:
    return PostgresCodeVectorStoreProvider()
