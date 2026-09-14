import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class OpenAIChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: list[OpenAIChatMessage]
    stream: bool = False
    temperature: float = 0.7


class OpenAIChoiceMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class OpenAIChoice(BaseModel):
    index: int = 0
    message: OpenAIChoiceMessage
    finish_reason: str = "stop"


class OpenAIChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[OpenAIChoice]
