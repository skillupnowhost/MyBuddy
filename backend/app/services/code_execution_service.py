import asyncio
import re
import sys
from dataclasses import dataclass

MAX_OUTPUT_CHARS = 2000
EXECUTION_TIMEOUT_SECONDS = 5.0

_PYTHON_CODE_BLOCK_PATTERN = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)

# A generated snippet is executed automatically, with no per-reply confirmation — reasonable
# for a local, single-user assistant running snippets the user themselves asked for, but only
# for code that can't reach outside the interpreter. Anything touching the filesystem, a
# process, the network, or dynamic eval/exec is skipped rather than risking an LLM-authored
# side effect running unattended. This is a safety net against accidental generation, not a
# hardened sandbox against a deliberately adversarial payload.
_UNSAFE_PATTERNS = re.compile(
    r"\b(os\.|subprocess|shutil|socket|urllib|requests\.|eval\(|exec\(|__import__|open\(|"
    r"sys\.exit|popen|remove\(|rmtree|unlink\(|rmdir\(|ctypes|pathlib)\b"
)


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    timed_out: bool


async def run_python_snippet(code: str, timeout: float = EXECUTION_TIMEOUT_SECONDS) -> ExecutionResult:
    """Runs a short, untrusted Python snippet in a fresh interpreter subprocess so a generated
    code block's real output can be shown instead of an LLM's guess at what it would print — a
    small local model's guess is often wrong (it isn't actually running the code either way).

    Local-machine trust model, not a hardened sandbox: this is the same interpreter the user
    already runs their own scripts with, just isolated (-I, ignores site-packages/PYTHONPATH)
    and given no stdin — an input() call fails fast with EOFError instead of hanging the
    request — with a hard wall-clock timeout so a generated infinite loop can't hang a reply.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            code,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, NotImplementedError):
        # NotImplementedError: Windows' default SelectorEventLoop can't spawn subprocesses
        # (only ProactorEventLoop can) — whichever loop this process ends up running under is
        # an environment detail, not something a generated code block should ever be able to
        # turn into a dead chat stream. Degrade the same way a real OSError does: no output
        # section, reply still completes normally.
        return ExecutionResult(stdout="", stderr="", timed_out=False)

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ExecutionResult(stdout="", stderr="", timed_out=True)

    stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
    stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
    return ExecutionResult(stdout=stdout, stderr=stderr, timed_out=False)


async def maybe_run_code_and_format_output(reply: str) -> str | None:
    """Finds the first python code block in `reply`, runs it, and returns a ready-to-append
    "**Output**" markdown section with the real result — or None when there's nothing worth
    showing: no code block, unsafe-looking code (skipped, see _UNSAFE_PATTERNS), a snippet that
    blocks on input(), a timeout, or a run that produces neither output nor an error.
    """
    match = _PYTHON_CODE_BLOCK_PATTERN.search(reply)
    if not match:
        return None
    code = match.group(1)
    if _UNSAFE_PATTERNS.search(code):
        return None

    result = await run_python_snippet(code)
    if result.timed_out:
        return None
    if "EOFError" in result.stderr:
        # input() writes its prompt to stdout before blocking on stdin, so a prompt fragment
        # (e.g. "Enter a number: ") can land in stdout even though the run never completed —
        # showing that fragment as "the output" would be actively misleading, not just empty.
        return None
    if result.stdout.strip():
        # Tagged "text", not bare — an untagged fence gets no `language-*` class from
        # ReactMarkdown, so it would render as tiny inline code instead of the same
        # syntax-highlighted, header-and-copy-button box as the code above it.
        return f"\n\n**Output**\n```text\n{result.stdout.strip()}\n```"
    if result.stderr.strip():
        error_line = result.stderr.strip().splitlines()[-1]
        return f"\n\n**Output**\n```text\n{error_line}\n```"
    return None
