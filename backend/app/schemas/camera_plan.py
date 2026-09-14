import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CameraMotionType = Literal[
    "STATIC", "PAN", "TILT", "ZOOM_IN", "ZOOM_OUT", "DOLLY_IN", "DOLLY_OUT",
    "TRUCK_LEFT", "TRUCK_RIGHT", "ORBIT", "CRANE", "HANDHELD", "DRONE", "TRACKING",
    "RACK_FOCUS", "PUSH_IN", "PULL_OUT", "ROTATE_360", "FIRST_PERSON", "THIRD_PERSON",
]


class CameraPlanCreate(BaseModel):
    storyboard_shot_id: uuid.UUID | None = None
    name: str | None = None
    motion_type: CameraMotionType = "STATIC"
    lens: str | None = None
    focal_length_mm: float | None = None
    aperture: float | None = None
    shutter_speed: str | None = None
    depth_of_field: str | None = None
    motion_path: str | None = None


class CameraPlanPatch(BaseModel):
    name: str | None = None
    motion_type: CameraMotionType | None = None
    lens: str | None = None
    focal_length_mm: float | None = None
    aperture: float | None = None
    shutter_speed: str | None = None
    depth_of_field: str | None = None
    motion_path: str | None = None


class CameraPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    storyboard_shot_id: uuid.UUID | None
    name: str | None
    motion_type: str
    lens: str | None
    focal_length_mm: float | None
    aperture: float | None
    shutter_speed: str | None
    depth_of_field: str | None
    motion_path: str | None
    created_at: datetime
