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

    # --- Vision (image/screenshot understanding) ---
    ollama_vision_model: str = "moondream"
    max_image_size_bytes: int = 10 * 1024 * 1024  # 10MB
    allowed_image_content_types: tuple[str, ...] = ("image/png", "image/jpeg", "image/webp", "image/gif")

    # --- Image generation ---
    image_gen_model: str = "stabilityai/sd-turbo"
    image_gen_default_steps: int = 4
    image_gen_max_steps: int = 20
    image_gen_default_width: int = 512
    image_gen_default_height: int = 512
    image_gen_max_width: int = 768
    image_gen_max_height: int = 768

    # --- Image editing (inpaint / outpaint / background removal) ---
    # No turbo-distilled inpainting model is as established as sd-turbo is for generation,
    # so this is honestly slower than image_gen_model on CPU — see imagegen/README.md.
    image_edit_model: str = "runwayml/stable-diffusion-inpainting"
    image_edit_default_steps: int = 20
    image_edit_max_steps: int = 30
    image_edit_max_outpaint_padding: int = 256
    image_edit_bg_removal_model: str = "u2net"

    # --- Video generation (MyBuddy Video, text-to-video) ---
    # Far heavier than image generation (diffusion over many frames, not one) — on this
    # project's CPU-only dev hardware this is architecture-complete but not runnable in any
    # practical sense; see video/README.md. num_frames/fps/steps caps exist so a request
    # can't accidentally ask for something that would never finish even on a GPU machine.
    video_gen_model: str = "damo-vilab/text-to-video-ms-1.7b"
    video_gen_default_steps: int = 25
    video_gen_max_steps: int = 50
    video_gen_default_width: int = 256
    video_gen_default_height: int = 256
    video_gen_max_width: int = 512
    video_gen_max_height: int = 512
    video_gen_default_num_frames: int = 16
    video_gen_max_num_frames: int = 64
    video_gen_fps: int = 8

    # --- MyBuddy CG: text/image -> 3D mesh generation (video/CG/VFX spec §11-13) ---
    # Shap-E via diffusers — text-to-3D and image-to-3D through the same library already
    # used for Image/Video, rather than a new ML stack. Same CPU-hardware caveat as
    # video_gen_*; see cg3d/README.md.
    cg3d_text_model: str = "openai/shap-e"
    cg3d_image_model: str = "openai/shap-e-img2img"
    cg3d_default_steps: int = 64
    cg3d_max_steps: int = 128
    cg3d_default_guidance_scale: float = 15.0

    # --- StoryboardGenerator (video/CG/VFX spec §7) ---
    # Pure LLM structured output, same fenced-block + Pydantic-validation + repair-retry
    # convention as Vector's generate_scene — no image/video model involved, so this reuses
    # settings.ollama_model directly rather than a dedicated capability.
    storyboard_max_shots: int = 30
    storyboard_max_retries: int = 1

    # --- Vector graphics ---
    # No dedicated model setting: generation is plain JSON-producing text generation, not a
    # specialized capability like vision/code, so it reuses settings.ollama_model directly
    # rather than pulling a third model at startup.
    vector_max_objects_per_document: int = 100  # hard ceiling; must stay >= every purpose's max_objects below
    vector_max_retries: int = 1  # JSON-repair retry count on invalid scene/operation output
    vector_canvas_max_width: int = 2000
    vector_canvas_max_height: int = 2000
    # Per-purpose defaults for MyBuddy Illustrator presets (General/Illustration/Logo/Icon) —
    # used only when a request doesn't specify canvas_width/height explicitly. Still capped by
    # vector_canvas_max_width/height and vector_max_objects_per_document above regardless.
    vector_purpose_defaults: dict = {
        "GENERAL": {"canvas_width": 400, "canvas_height": 400, "max_objects": 50},
        "ILLUSTRATION": {"canvas_width": 600, "canvas_height": 600, "max_objects": 80},
        "LOGO": {"canvas_width": 200, "canvas_height": 200, "max_objects": 15},
        "ICON": {"canvas_width": 64, "canvas_height": 64, "max_objects": 8},
    }

    # --- Animation ---
    animation_max_duration_ms: int = 10000
    animation_max_keyframes: int = 200
    animation_default_frame_rate: int = 30
    animation_default_duration_ms: int = 2000

    # --- Motion ---
    motion_max_total_duration_ms: int = 30000
    motion_max_clips: int = 20

    # --- Creative Director ---
    creative_max_assets_per_project: int = 50

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
