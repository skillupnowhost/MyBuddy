import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CG3D_SCRIPT = _REPO_ROOT / "cg3d" / "scripts" / "generate.py"
_CG3D_VENV_PYTHON = _REPO_ROOT / "cg3d" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_model_3d_generation_job(
    job_id: str,
    user_id: str,
    prompt: str | None,
    source_image_path: str | None,
    steps: int,
    guidance_scale: float,
    seed: int | None,
) -> subprocess.Popen:
    """Launches 3D mesh generation as a genuinely separate OS process — same reasoning as
    image_generation_service.launch_image_generation_job / video_generation_service. Uses
    cg3d/.venv if it's been set up (see cg3d/README.md); falls back to the backend's own
    interpreter otherwise, which will fail fast with a clear ImportError if torch/diffusers
    aren't installed there."""
    python = str(_CG3D_VENV_PYTHON) if _CG3D_VENV_PYTHON.exists() else sys.executable

    storage_dir = os.path.abspath(settings.storage_dir)

    command = [
        python,
        str(_CG3D_SCRIPT),
        "--job-id", job_id,
        "--user-id", user_id,
        "--steps", str(steps),
        "--guidance-scale", str(guidance_scale),
        "--text-model", settings.cg3d_text_model,
        "--image-model", settings.cg3d_image_model,
        "--storage-dir", storage_dir,
        "--database-url", settings.database_url,
    ]
    if prompt:
        command += ["--prompt", prompt]
    if source_image_path:
        command += ["--source-image-path", source_image_path]
    if seed is not None:
        command += ["--seed", str(seed)]

    return subprocess.Popen(
        command,
        cwd=str(_REPO_ROOT / "cg3d"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_model_3d_generation_job(pid: int) -> bool:
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
