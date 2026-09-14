import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AnimationEasing = Literal["LINEAR", "EASE_IN", "EASE_OUT", "EASE_IN_OUT"]


# Same two-layer pattern as VectorOperationInput/VectorOperation: the LLM only ever sees/
# produces object_index (position in the numbered object list it was shown); animation_service
# resolves it to a real object_id before a keyframe is ever written. Manual (non-AI) keyframe
# creation builds the resolved shape directly, since the caller already has the real object_id.
class AnimationKeyframeInput(BaseModel):
    object_index: int
    time_ms: int
    prop: str
    value: float | str
    easing: AnimationEasing = "LINEAR"


class AnimationKeyframeCreate(BaseModel):
    object_id: uuid.UUID
    time_ms: int
    prop: str
    value: float | str
    easing: AnimationEasing = "LINEAR"


class AnimationKeyframeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    time_ms: int
    prop: str
    value: float | str
    easing: AnimationEasing
    created_at: datetime


class AnimationDocumentCreate(BaseModel):
    vector_document_id: uuid.UUID
    prompt: str
    duration_ms: int | None = None
    frame_rate: int | None = None
    loop: bool = True


class AnimationDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vector_document_id: uuid.UUID
    title: str
    frame_rate: int
    duration_ms: int
    loop: bool
    keyframes: list[AnimationKeyframeRead] = []
    created_at: datetime
    updated_at: datetime


class AnimationKeyframePatch(BaseModel):
    time_ms: int | None = None
    prop: str | None = None
    value: float | str | None = None
    easing: AnimationEasing | None = None
