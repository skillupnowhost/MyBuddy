import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    step_index: int
    assistant_reply: str
    tool_name: str
    tool_result: str
    created_at: datetime
