import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRAIN_SCRIPT = _REPO_ROOT / "training" / "scripts" / "train_lora.py"
_TRAIN_VENV_PYTHON = _REPO_ROOT / "training" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_training_job(
    job_id: str, dataset_path: str, base_model: str, output_dir: str, capability: str = "TEXT"
) -> subprocess.Popen:
    """Launches training as a genuinely separate OS process — never inside the API process,
    so a long-running fine-tune can't block normal requests and a crash there can't take
    down the API. Uses training/.venv if it's been set up (see training/README.md); falls
    back to the backend's own interpreter otherwise, which will fail fast with a clear
    ImportError if torch/transformers/peft aren't installed there — that's the correct
    behavior, not a bug, until the training environment is actually provisioned."""
    python = str(_TRAIN_VENV_PYTHON) if _TRAIN_VENV_PYTHON.exists() else sys.executable

    return subprocess.Popen(
        [
            python,
            str(_TRAIN_SCRIPT),
            "--job-id", job_id,
            "--dataset", dataset_path,
            "--base-model", base_model,
            "--output-dir", output_dir,
            "--database-url", settings.database_url,
            "--capability", capability,
        ],
        cwd=str(_REPO_ROOT / "training"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_training_job(pid: int) -> bool:
    """Best-effort termination of a running training process by OS pid. Returns False if the
    process is already gone (job likely finished/crashed on its own between the status check
    and this call) rather than raising — that's a normal race, not an error."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import os
            import signal

            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
