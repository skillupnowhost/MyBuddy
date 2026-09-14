import asyncio
import os
import shutil
import sys
import tempfile
import time

from app.core.config import get_settings
from app.services.sandbox_provider import SandboxProvider, SandboxResult, UnsupportedLanguage

settings = get_settings()

_LANGUAGE_FILES = {
    "python": "script.py",
}


def _command_for(language: str, script_path: str) -> list[str]:
    if language == "python":
        return [sys.executable, script_path]
    raise UnsupportedLanguage(f"No launch command configured for language '{language}'.")


def _truncate(data: bytes, max_bytes: int) -> tuple[str, bool]:
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    return text, truncated


class SubprocessSandboxProvider(SandboxProvider):
    """Runs submitted code as a plain OS subprocess. This is deliberately weaker than a
    container-based sandbox and MUST stay admin-gated at every call site until a
    container-backed provider (see SandboxProvider) replaces it.

    What this DOES provide:
      - a hard wall-clock timeout (settings.sandbox_timeout_seconds) — the process is
        killed and the result marked timed_out=True if it's exceeded;
      - a fresh, empty temp working directory per run, deleted afterward;
      - a minimal, explicitly-built environment (never os.environ.copy()) so secrets
        like DATABASE_URL/JWT_SECRET never appear in the child process's environment;
      - stdout/stderr each truncated to settings.sandbox_max_output_bytes.

    What this does NOT provide (stated plainly, not glossed over):
      - no filesystem jail — the child can read/write anything the backend's OS user
        can, not just its own temp directory;
      - no network isolation — the child can make outbound network requests, including
        (in the Docker deployment) to this stack's own Postgres/Ollama containers if
        they're reachable on the same network;
      - no memory/CPU cap beyond the wall-clock timeout — a process that allocates a
        lot of memory quickly is not stopped before it does so;
      - no uid/gid drop, no seccomp/AppArmor/similar profile.

    This is why code execution is restricted to ADMIN accounts only in v1: it's a tool
    for a trusted operator to run their own snippets, not a multi-tenant-safe execution
    service.
    """

    async def run(self, language: str, source: str) -> SandboxResult:
        if language not in settings.sandbox_allowed_languages:
            raise UnsupportedLanguage(f"Language '{language}' is not enabled for execution.")

        filename = _LANGUAGE_FILES.get(language)
        if filename is None:
            raise UnsupportedLanguage(f"Language '{language}' has no sandbox runner configured.")

        work_dir = tempfile.mkdtemp(prefix="mybuddy-sandbox-")
        try:
            script_path = os.path.join(work_dir, filename)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(source)

            command = _command_for(language, script_path)

            env = {"PATH": os.environ.get("PATH", "")}
            if sys.platform == "win32":
                # Required for the interpreter itself to start correctly on Windows.
                env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")

            start = time.monotonic()
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=work_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            timed_out = False
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=settings.sandbox_timeout_seconds
                )
            except asyncio.TimeoutError:
                timed_out = True
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()

            duration_ms = int((time.monotonic() - start) * 1000)

            stdout, stdout_truncated = _truncate(stdout_bytes, settings.sandbox_max_output_bytes)
            stderr, stderr_truncated = _truncate(stderr_bytes, settings.sandbox_max_output_bytes)

            return SandboxResult(
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
                timed_out=timed_out,
                duration_ms=duration_ms,
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


def get_sandbox_provider() -> SandboxProvider:
    return SubprocessSandboxProvider()
