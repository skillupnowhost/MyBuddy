import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DatasetStatus = Literal["UPLOADED", "VALIDATED", "INVALID"]
TrainingJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
ModelStatus = Literal["EXPERIMENTAL", "CANARY", "STAGING", "PRODUCTION", "ARCHIVED", "REJECTED"]


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    num_examples: int | None
    status: DatasetStatus
    error_message: str | None
    created_at: datetime


class TrainingJobCreate(BaseModel):
    dataset_id: uuid.UUID
    base_model: str
    epochs: int = 1
    learning_rate: float = 2e-4
    lora_r: int = 8
    capability: Literal["TEXT", "CODE", "VISION", "EMBEDDING"] = "TEXT"


class TrainingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    base_model: str
    status: TrainingJobStatus
    config: dict
    output_path: str | None
    error_message: str | None
    eval_metrics: dict | None
    created_at: datetime
    completed_at: datetime | None


class RegisteredModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    version: str
    base_model: str
    capability: str
    provider: str
    quantization: str | None
    location: str
    status: ModelStatus
    eval_score: float | None
    promoted_at: datetime | None
    created_at: datetime


class ModelPromotion(BaseModel):
    status: ModelStatus
