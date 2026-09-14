import re
import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

VectorObjectType = Literal["RECT", "CIRCLE", "ELLIPSE", "LINE", "POLYGON", "PATH", "TEXT"]

_COLOR_NAMES = {
    "black", "white", "red", "green", "blue", "yellow", "orange", "purple", "pink", "brown",
    "gray", "grey", "cyan", "magenta", "lime", "navy", "teal", "maroon", "olive", "silver", "gold",
}
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# The actual security boundary for path data — no quotes/angle-brackets/etc. can ever pass
# this, which is what makes emitting it as a raw SVG attribute value safe.
_PATH_DATA_RE = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9\s,.\-]+$")


def _validate_color(value: str) -> str:
    if value == "none":
        return value
    if _HEX_COLOR_RE.match(value):
        return value
    if value.lower() in _COLOR_NAMES:
        return value.lower()
    raise ValueError(f"'{value}' is not a valid color (use 'none', a #hex value, or a common CSS color name)")


class _StyledProps(BaseModel):
    fill: str = "black"
    stroke: str = "none"
    stroke_width: float = 1.0
    opacity: float = 1.0

    @field_validator("fill", "stroke")
    @classmethod
    def _check_color(cls, v: str) -> str:
        return _validate_color(v)

    @field_validator("opacity")
    @classmethod
    def _check_opacity(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("opacity must be between 0 and 1")
        return v


class RectProps(_StyledProps):
    object_type: Literal["RECT"] = "RECT"
    x: float
    y: float
    width: float
    height: float
    rx: float = 0


class CircleProps(_StyledProps):
    object_type: Literal["CIRCLE"] = "CIRCLE"
    cx: float
    cy: float
    r: float


class EllipseProps(_StyledProps):
    object_type: Literal["ELLIPSE"] = "ELLIPSE"
    cx: float
    cy: float
    rx: float
    ry: float


class LineProps(_StyledProps):
    object_type: Literal["LINE"] = "LINE"
    x1: float
    y1: float
    x2: float
    y2: float


class PolygonProps(_StyledProps):
    object_type: Literal["POLYGON"] = "POLYGON"
    points: list[tuple[float, float]]

    @field_validator("points")
    @classmethod
    def _check_points(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(v) < 3:
            raise ValueError("a polygon needs at least 3 points")
        return v


class PathProps(_StyledProps):
    object_type: Literal["PATH"] = "PATH"
    d: str

    @field_validator("d")
    @classmethod
    def _check_d(cls, v: str) -> str:
        if not v or not _PATH_DATA_RE.match(v):
            raise ValueError("path data contains characters outside the allowed path-command set")
        return v


class TextProps(_StyledProps):
    object_type: Literal["TEXT"] = "TEXT"
    x: float
    y: float
    content: str
    font_size: float = 16


VectorObjectProps = Annotated[
    Union[RectProps, CircleProps, EllipseProps, LineProps, PolygonProps, PathProps, TextProps],
    Field(discriminator="object_type"),
]


class VectorObjectCreate(BaseModel):
    props: VectorObjectProps
    z_index: int = 0
    layer_name: str = "default"


class VectorObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_type: str
    z_index: int
    layer_name: str
    props: dict
    created_at: datetime
    updated_at: datetime


VectorDocumentPurpose = Literal["GENERAL", "ILLUSTRATION", "LOGO", "ICON"]


class VectorDocumentCreate(BaseModel):
    prompt: str
    purpose: VectorDocumentPurpose = "GENERAL"
    # None means "use this purpose's default" (see settings.vector_purpose_defaults) rather
    # than hard-coding General's 400x400 here — an explicit value still always overrides it.
    canvas_width: int | None = None
    canvas_height: int | None = None


class VectorDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    purpose: VectorDocumentPurpose
    canvas_width: int
    canvas_height: int
    background_color: str | None
    objects: list[VectorObjectRead] = []
    created_at: datetime
    updated_at: datetime


class VectorEditRequest(BaseModel):
    instruction: str


class VectorObjectPatch(BaseModel):
    prop: str
    value: float | str


# --- Structured edit operations ---
#
# Two layers: the LLM only ever sees/produces *Input variants, which reference an object by
# its position (object_index) in the numbered list it was shown — small local models handle
# a short integer far more reliably than reproducing a UUID verbatim. vector_service resolves
# an index back to a real object_id before apply_operation ever runs, producing the "resolved"
# operations below. Manual (non-AI) edits build a resolved operation directly, since the
# caller already has the real object_id from the URL.


class SetPropOpInput(BaseModel):
    op: Literal["SET_PROP"] = "SET_PROP"
    object_index: int
    prop: str
    value: float | str


class DeleteObjectOpInput(BaseModel):
    op: Literal["DELETE_OBJECT"] = "DELETE_OBJECT"
    object_index: int


class ReorderOpInput(BaseModel):
    op: Literal["REORDER"] = "REORDER"
    object_index: int
    z_index: int


class AddObjectOpInput(BaseModel):
    op: Literal["ADD_OBJECT"] = "ADD_OBJECT"
    object: VectorObjectCreate


VectorOperationInput = Annotated[
    Union[SetPropOpInput, DeleteObjectOpInput, ReorderOpInput, AddObjectOpInput],
    Field(discriminator="op"),
]


class SetPropOp(BaseModel):
    op: Literal["SET_PROP"] = "SET_PROP"
    object_id: uuid.UUID
    prop: str
    value: float | str


class DeleteObjectOp(BaseModel):
    op: Literal["DELETE_OBJECT"] = "DELETE_OBJECT"
    object_id: uuid.UUID


class ReorderOp(BaseModel):
    op: Literal["REORDER"] = "REORDER"
    object_id: uuid.UUID
    z_index: int


class AddObjectOp(BaseModel):
    op: Literal["ADD_OBJECT"] = "ADD_OBJECT"
    object: VectorObjectCreate


VectorOperation = Annotated[
    Union[SetPropOp, DeleteObjectOp, ReorderOp, AddObjectOp],
    Field(discriminator="op"),
]
