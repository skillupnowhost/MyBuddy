import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IMAGEGEN_SCRIPT = _REPO_ROOT / "imagegen" / "scripts" / "edit_image.py"
_IMAGEGEN_VENV_PYTHON = _REPO_ROOT / "imagegen" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_image_edit_job(
    job_id: str,
    user_id: str,
    operation: str,
    source_image_id: str,
    mask_image_id: str | None,
    prompt: str | None,
    negative_prompt: str | None,
    steps: int,
    outpaint_top: int,
    outpaint_bottom: int,
    outpaint_left: int,
    outpaint_right: int,
) -> subprocess.Popen:
    """Launches image editing as a genuinely separate OS process, same reasoning as
    image_generation_service.launch_image_generation_job — reuses the same imagegen/.venv
    (a second script in that directory, not a second venv). Falls back to the backend's own
    interpreter if the venv isn't provisioned, which will fail fast with a clear ImportError."""
    python = str(_IMAGEGEN_VENV_PYTHON) if _IMAGEGEN_VENV_PYTHON.exists() else sys.executable

    storage_dir = os.path.abspath(settings.storage_dir)

    command = [
        python,
        str(_IMAGEGEN_SCRIPT),
        "--job-id", job_id,
        "--user-id", user_id,
        "--operation", operation.lower(),
        "--source-image-id", source_image_id,
        "--steps", str(steps),
        "--outpaint-top", str(outpaint_top),
        "--outpaint-bottom", str(outpaint_bottom),
        "--outpaint-left", str(outpaint_left),
        "--outpaint-right", str(outpaint_right),
        "--model", settings.image_edit_model,
        "--bg-removal-model", settings.image_edit_bg_removal_model,
        "--storage-dir", storage_dir,
        "--database-url", settings.database_url,
    ]
    if mask_image_id:
        command += ["--mask-image-id", mask_image_id]
    if prompt:
        command += ["--prompt", prompt]
    if negative_prompt:
        command += ["--negative-prompt", negative_prompt]

    return subprocess.Popen(
        command,
        cwd=str(_REPO_ROOT / "imagegen"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_image_edit_job(pid: int) -> bool:
    """Best-effort termination by OS pid — same shape as image_generation_service's own
    local copy; kept local rather than a shared helper since these subsystems are otherwise
    independent."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
