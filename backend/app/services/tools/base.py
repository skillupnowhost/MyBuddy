import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ToolCallResult:
    tool_name: str
    result: str
    # Set only by tools that produce a viewable image (currently just generate_image) — lets
    # chat_service attach the generated Image to the assistant's persisted message without
    # every other tool's plain-text result needing to carry this field.
    image_id: uuid.UUID | None = None


@dataclass
class ToolContext:
    """Per-request context for tools that need to read the calling user's own data (e.g.
    read_code_file, search_memories) — never passed to the model, never used to widen a
    tool's access beyond that one user's own rows. Tools that don't need it (calculator,
    current_datetime) simply ignore the parameter."""

    db: "Session"
    user_id: uuid.UUID


class Tool(ABC):
    """A safe, deterministic capability the model can invoke mid-conversation.

    Never wraps arbitrary code execution, shell access, network access, or a generic/
    free-form database query — every implementation must be something safe to run
    unattended for any authenticated user, scoped to that user's own data only.
    """

    name: str
    description: str

    @abstractmethod
    async def run(self, args: dict, context: ToolContext | None = None) -> str:
        ...
