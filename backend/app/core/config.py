from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://mybuddy:change_me@localhost:5432/mybuddy"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_embedding_model: str = "all-minilm"

    frontend_origin: str = "http://localhost:3000"

    # --- RAG / documents ---
    storage_dir: str = "./data/documents"
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20MB
    allowed_upload_content_types: tuple[str, ...] = (
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 150
    rag_top_k: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
