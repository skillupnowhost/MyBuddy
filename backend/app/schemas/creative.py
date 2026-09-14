import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.vector import VectorDocumentPurpose, _validate_color

CreativeAssetType = Literal["VECTOR", "ANIMATION", "MOTION"]


def _validate_optional_color(v: str | None) -> str | None:
    if v is None:
        return v
    return _validate_color(v)


class BrandKitCreate(BaseModel):
    name: str
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    font_family: str | None = None

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def _check_color(cls, v: str | None) -> str | None:
        return _validate_optional_color(v)


class BrandKitPatch(BaseModel):
    name: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    font_family: str | None = None

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def _check_color(cls, v: str | None) -> str | None:
        return _validate_optional_color(v)


class BrandKitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    font_family: str | None
    created_at: datetime
    updated_at: datetime


class CreativeAssetAttach(BaseModel):
    asset_type: CreativeAssetType
    asset_id: uuid.UUID
    label: str | None = None


class CreativeAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_type: CreativeAssetType
    asset_id: uuid.UUID
    label: str | None
    created_at: datetime


class CreativeProjectCreate(BaseModel):
    title: str
    brand_kit_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None


class CreativeProjectPatch(BaseModel):
    title: str | None = None
    brand_kit_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None


class CreativeProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    brand_kit_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    assets: list[CreativeAssetRead] = []
    created_at: datetime
    updated_at: datetime


class CreativeGenerateAssetRequest(BaseModel):
    prompt: str
    purpose: VectorDocumentPurpose = "GENERAL"
    label: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
