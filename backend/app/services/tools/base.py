from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolCallResult:
    tool_name: str
    result: str


class Tool(ABC):
    """A safe, deterministic capability the model can invoke mid-conversation.

    Never wraps arbitrary code execution or shell access — every implementation must be
    something safe to run unattended for any authenticated user.
    """

    name: str
    description: str

    @abstractmethod
    def run(self, args: dict) -> str:
        ...
