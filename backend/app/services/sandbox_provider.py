from abc import ABC, abstractmethod
from dataclasses import dataclass


class UnsupportedLanguage(Exception):
    pass


@dataclass
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    duration_ms: int


class SandboxProvider(ABC):
    """Abstraction over 'run this code somewhere and get output back.'

    v1's only implementation (SubprocessSandboxProvider) isolates via OS process + a
    fresh temp directory + a wall-clock timeout + a restricted environment — NOT a
    container. See that class's docstring for the exact security boundary this does and
    does not provide, and why every call site gates it to ADMIN users. A future
    container-backed provider (e.g. a DockerSandboxProvider) drops in here with zero
    call-site changes, same as every other provider abstraction in this codebase.
    """

    @abstractmethod
    async def run(self, language: str, source: str) -> SandboxResult:
        ...
