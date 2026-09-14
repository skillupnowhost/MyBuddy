import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# CameraPlanner (video/CG/VFX spec §10). Deliberately no numeric position/rotation/motion-path
# coordinates — those are only meaningful relative to a 3D scene, and no CG/3D system exists
# in this project yet (spec §11-13, not started). What's genuinely useful without one:
# structured cinematography intent (motion type, lens, focal length, aperture, shutter,
# depth of field) instead of a single free-text "camera" string — see
# StoryboardShot.camera/lens, which this is a structured, optional companion to, not a
# replacement for.
CAMERA_MOTION_TYPES = (
    "STATIC", "PAN", "TILT", "ZOOM_IN", "ZOOM_OUT", "DOLLY_IN", "DOLLY_OUT",
    "TRUCK_LEFT", "TRUCK_RIGHT", "ORBIT", "CRANE", "HANDHELD", "DRONE", "TRACKING",
    "RACK_FOCUS", "PUSH_IN", "PULL_OUT", "ROTATE_360", "FIRST_PERSON", "THIRD_PERSON",
)


class CameraPlan(Base):
    __tablename__ = "camera_plans"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storyboard_shot_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("storyboard_shots.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    motion_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STATIC")
    lens: Mapped[str | None] = mapped_column(String(100), nullable=True)
    focal_length_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    aperture: Mapped[float | None] = mapped_column(Float, nullable=True)
    shutter_speed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    depth_of_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    motion_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
