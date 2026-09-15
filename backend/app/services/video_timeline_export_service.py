import json
import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXPORT_SCRIPT = _REPO_ROOT / "video" / "scripts" / "export_timeline.py"
_VIDEO_VENV_PYTHON = _REPO_ROOT / "video" / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)


def launch_timeline_export_job(
    job_id: str, user_id: str, clips: list[dict]
) -> subprocess.Popen:
    """Launches timeline export (trim + concatenate) as a genuinely separate OS process —
    same reasoning as video_generation_service.launch_video_generation_job. Shares video/'s
    venv (export_timeline.py lives alongside generate.py/edit_video.py). Pure frame I/O via
    imageio, no ML model — CPU-fast, actually completes on this project's hardware, same as
    REMOVE_BACKGROUND/COLOR_GRADE. `clips` is a plain list of
    {"storage_path", "trim_start_seconds", "trim_end_seconds"} dicts, already resolved and
    ordered by the caller — this script never queries the database for anything but its own
    job status."""
    python = str(_VIDEO_VENV_PYTHON) if _VIDEO_VENV_PYTHON.exists() else sys.executable

    storage_dir = os.path.abspath(settings.storage_dir)

    command = [
        python,
        str(_EXPORT_SCRIPT),
        "--job-id", job_id,
        "--user-id", user_id,
        "--clips-json", json.dumps(clips),
        "--storage-dir", storage_dir,
        "--database-url", settings.database_url,
    ]

    return subprocess.Popen(
        command,
        cwd=str(_REPO_ROOT / "video"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cancel_timeline_export_job(pid: int) -> bool:
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
