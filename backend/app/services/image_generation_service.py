import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IMAGEGEN_SCRIPT = _REPO_ROOT / "imagegen" / "scripts" / "generate.py"
_IMAGEGEN_VENV_PYTHON = _REPO_ROOT / "imagegen" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_image_generation_job(
    job_id: str,
    user_id: str,
    prompt: str,
    negative_prompt: str | None,
    width: int,
    height: int,
    steps: int,
    seed: int | None,
) -> subprocess.Popen:
    """Launches image generation as a genuinely separate OS process — never inside the API
    process, same reasoning as training_service.launch_training_job. Uses imagegen/.venv if
    it's been set up (see imagegen/README.md); falls back to the backend's own interpreter
    otherwise, which will fail fast with a clear ImportError if torch/diffusers aren't
    installed there — that's the correct behavior, not a bug, until the image generation
    environment is actually provisioned."""
    python = str(_IMAGEGEN_VENV_PYTHON) if _IMAGEGEN_VENV_PYTHON.exists() else sys.executable

    # storage_dir may be relative (e.g. the default "./data") — resolve it against this
    # process's cwd before handing it to a child process that runs with a different cwd
    # (imagegen/), or the child would look for it in the wrong place.
    storage_dir = os.path.abspath(settings.storage_dir)

    command = [
        python,
        str(_IMAGEGEN_SCRIPT),
        "--job-id", job_id,
        "--user-id", user_id,
        "--prompt", prompt,
        "--width", str(width),
        "--height", str(height),
        "--steps", str(steps),
        "--model", settings.image_gen_model,
        "--storage-dir", storage_dir,
        "--database-url", settings.database_url,
    ]
    if negative_prompt:
        command += ["--negative-prompt", negative_prompt]
    if seed is not None:
        command += ["--seed", str(seed)]

    return subprocess.Popen(
        command,
        cwd=str(_REPO_ROOT / "imagegen"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_image_generation_job(pid: int) -> bool:
    """Best-effort termination by OS pid. Returns False if the process is already gone (job
    likely finished/crashed on its own between the status check and this call) rather than
    raising — that's a normal race, not an error. Same shape as
    training_service.cancel_training_job; kept as a small local duplicate rather than a
    shared helper since these two subsystems are otherwise independent."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import signal

            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
