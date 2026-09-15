import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VIDEO_EDIT_SCRIPT = _REPO_ROOT / "video" / "scripts" / "edit_video.py"
_VIDEO_VENV_PYTHON = _REPO_ROOT / "video" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_video_edit_job(
    job_id: str,
    user_id: str,
    operation: str,
    source_video_path: str,
    background_color: str,
    mask_image_path: str | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    steps: int | None = None,
    background_image_path: str | None = None,
) -> subprocess.Popen:
    """Launches video editing as a genuinely separate OS process — same reasoning as
    video_generation_service.launch_video_generation_job. Shares video/'s venv (edit_video.py
    lives alongside generate.py, same as imagegen/'s generate.py + edit_image.py).
    REMOVE_BACKGROUND and REPLACE_ENVIRONMENT use rembg (CPU-fast, no GPU dependency —
    actually complete on this project's hardware); REMOVE_OBJECT reuses the SD inpainting
    pipeline (GPU-heavy, same caveat as generate.py) applied per-frame with
    mask_image_path."""
    python = str(_VIDEO_VENV_PYTHON) if _VIDEO_VENV_PYTHON.exists() else sys.executable

    storage_dir = os.path.abspath(settings.storage_dir)

    command = [
        python,
        str(_VIDEO_EDIT_SCRIPT),
        "--job-id", job_id,
        "--user-id", user_id,
        "--operation", operation,
        "--source-video-path", source_video_path,
        "--background-color", background_color,
        "--bg-removal-model", settings.video_edit_bg_removal_model,
        "--inpaint-model", settings.image_edit_model,
        "--storage-dir", storage_dir,
        "--database-url", settings.database_url,
    ]
    if mask_image_path:
        command += ["--mask-image-path", mask_image_path]
    if prompt:
        command += ["--prompt", prompt]
    if negative_prompt:
        command += ["--negative-prompt", negative_prompt]
    if steps is not None:
        command += ["--steps", str(steps)]
    if background_image_path:
        command += ["--background-image-path", background_image_path]

    return subprocess.Popen(
        command,
        cwd=str(_REPO_ROOT / "video"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_video_edit_job(pid: int) -> bool:
    """Best-effort termination by OS pid — same shape as
    video_generation_service.cancel_video_generation_job."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
