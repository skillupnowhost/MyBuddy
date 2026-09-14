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

    # --- Admin ---
    # Comma-separated emails auto-promoted to ADMIN on registration. Empty by default —
    # set this before the first registration to bootstrap an admin account.
    admin_emails: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    # --- RAG / documents ---
    storage_dir: str = "./data"
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

    # --- Code (RAG + editor) ---
    ollama_code_model: str = "qwen2.5-coder:1.5b"
    code_max_zip_size_bytes: int = 25 * 1024 * 1024  # 25MB zip upload cap
    code_max_extracted_size_bytes: int = 100 * 1024 * 1024  # zip-bomb guard on total uncompressed bytes
    code_max_files_per_project: int = 2000
    code_max_file_size_bytes: int = 1 * 1024 * 1024  # reject/skip any single file bigger than this
    code_max_compression_ratio: int = 100  # reject an entry if uncompressed/compressed exceeds this
    code_chunk_size_chars: int = 1000
    code_chunk_overlap_chars: int = 150
    code_rag_top_k: int = 6
    code_allowed_extensions: tuple[str, ...] = (
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php",
        ".c", ".h", ".cpp", ".hpp", ".cs", ".kt", ".swift", ".md", ".txt", ".json",
        ".yaml", ".yml", ".toml", ".sql", ".html", ".css",
    )
    code_excluded_dir_names: tuple[str, ...] = (
        "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next",
    )

    # --- Sandbox (code execution, ADMIN-only) ---
    # This runs submitted code as a plain OS subprocess, not a container — no filesystem
    # jail, no network isolation, no memory/CPU cap beyond the timeout. See
    # SubprocessSandboxProvider's docstring for the full security boundary. That is why
    # every sandbox endpoint requires ADMIN, not just an authenticated user.
    sandbox_enabled: bool = True
    sandbox_timeout_seconds: int = 10
    sandbox_max_output_bytes: int = 64 * 1024  # 64KB, stdout and stderr each
    sandbox_allowed_languages: tuple[str, ...] = ("python",)


@lru_cache
def get_settings() -> Settings:
    return Settings()
