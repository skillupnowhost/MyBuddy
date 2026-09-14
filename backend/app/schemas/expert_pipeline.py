import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExpertPipelineStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    step_index: int
    step_type: str
    instruction: str
    model: str
    raw_output: str
    verified_output: str
    created_at: datetime
