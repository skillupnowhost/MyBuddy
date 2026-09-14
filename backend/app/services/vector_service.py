import json
import re
import xml.sax.saxutils as saxutils

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.db.models.vector_document import VectorDocument
from app.db.models.vector_object import VectorObject
from app.schemas.vector import (
    AddObjectOp,
    AddObjectOpInput,
    DeleteObjectOp,
    DeleteObjectOpInput,
    ReorderOp,
    ReorderOpInput,
    SetPropOp,
    SetPropOpInput,
    VectorObjectCreate,
    VectorOperation,
    VectorOperationInput,
    _PATH_DATA_RE,
    _validate_color,
)

# Same fenced-block convention as app/services/tools/__init__.py's tool-call parsing, with
# real Pydantic schema validation and a repair retry layered on top (a scene graph is more
# failure-prone for a small local model than a single tool-call object).
_SCENE_BLOCK_RE = re.compile(r"```vector-scene\s*\n(.*?)\n```", re.DOTALL)
_OP_BLOCK_RE = re.compile(r"```vector-op\s*\n(.*?)\n```", re.DOTALL)

_SCENE_SYSTEM_PROMPT = """You are a vector scene generator. Given a description, respond with \
ONLY a fenced block in exactly this format (no other text):
```vector-scene
{{"objects": [{{"props": {{"object_type": "CIRCLE", "cx": 100, "cy": 100, "r": 40, "fill": "#3366cc"}}, "z_index": 0, "layer_name": "default"}}]}}
```
Valid object_type values and their props:
- RECT: x, y, width, height, rx (optional), fill, stroke, stroke_width, opacity
- CIRCLE: cx, cy, r, fill, stroke, stroke_width, opacity
- ELLIPSE: cx, cy, rx, ry, fill, stroke, stroke_width, opacity
- LINE: x1, y1, x2, y2, stroke, stroke_width, opacity
- POLYGON: points (list of [x, y] pairs, at least 3), fill, stroke, stroke_width, opacity
- PATH: d (SVG path data using only M/L/H/V/C/S/Q/T/A/Z commands and numbers), fill, stroke, stroke_width, opacity
- TEXT: x, y, content, font_size, fill
fill/stroke must be "none", a #hex color, or a common CSS color name. Use at most {max_objects} objects.
{purpose_guidance}"""

# MyBuddy Illustrator presets: GENERAL is an empty string, so a GENERAL request's prompt is
# byte-for-byte identical to Vector's original prompt — this phase changes nothing for
# existing documents/behavior. The other three only ever influence this generation prompt,
# never the stored object schema, edit mechanism, or renderer.
_PURPOSE_GUIDANCE: dict[str, str] = {
    "GENERAL": "",
    "ILLUSTRATION": "Create a richer, more detailed illustrative scene using varied shapes and "
    "paths, layered with sensible z-index ordering.",
    "LOGO": "Design a simple, bold, instantly recognizable logo mark. Prefer 2-4 objects, a "
    "limited color palette (2-3 colors), and clean geometric or iconic shapes — avoid fine "
    "detail that won't read at small sizes.",
    "ICON": "Design an extremely simple, single-color-friendly icon glyph readable at a small "
    "size. Prefer 1-4 objects and minimal detail.",
}

_EDIT_SYSTEM_PROMPT = """You are editing an existing vector scene. Here is the current scene \
as a numbered list of objects:
{object_list}

Respond with ONLY a fenced block in exactly this format (no other text):
```vector-op
{{"op": "SET_PROP", "object_index": 0, "prop": "fill", "value": "#ff0000"}}
```
Valid op values:
- SET_PROP: {{"op": "SET_PROP", "object_index": <int>, "prop": "<field name>", "value": <number or string>}}
- DELETE_OBJECT: {{"op": "DELETE_OBJECT", "object_index": <int>}}
- REORDER: {{"op": "REORDER", "object_index": <int>, "z_index": <int>}}
- ADD_OBJECT: {{"op": "ADD_OBJECT", "object": {{"props": {{...}}, "z_index": <int>, "layer_name": "default"}}}}
object_index refers to the position in the numbered list above. Only change what the \
instruction asks for."""


class VectorGenerationError(Exception):
    """Raised when the model can't be coaxed into a valid scene/operation within the retry
    budget — the caller must surface this clearly, never fall back to an empty/garbage
    document."""


class _SceneResponse(BaseModel):
    objects: list[VectorObjectCreate]


def _describe_objects(objects: list[VectorObject]) -> str:
    lines = []
    for i, obj in enumerate(objects):
        summary = ", ".join(f"{k}={v}" for k, v in obj.props.items() if k != "object_type")
        lines.append(f"{i}: {obj.object_type} ({summary})")
    return "\n".join(lines) or "(empty scene)"


async def generate_scene(
    llm_client, model: str, prompt: str, max_objects: int, max_retries: int, purpose: str = "GENERAL"
) -> list[VectorObjectCreate]:
    system_prompt = _SCENE_SYSTEM_PROMPT.format(
        max_objects=max_objects, purpose_guidance=_PURPOSE_GUIDANCE.get(purpose, "")
    ).rstrip()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    last_error: str | None = None
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```vector-scene block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _SCENE_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```vector-scene fenced block found"
            continue
        try:
            scene = _SceneResponse.model_validate(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        if len(scene.objects) > max_objects:
            last_error = f"too many objects ({len(scene.objects)} > {max_objects})"
            continue

        return scene.objects

    raise VectorGenerationError(
        f"The model could not produce a valid scene after {max_retries + 1} attempt(s): {last_error}"
    )


async def create_document_from_scene(
    db: Session,
    user_id,
    llm_client,
    model: str,
    prompt: str,
    purpose: str,
    canvas_width: int,
    canvas_height: int,
    max_objects: int,
    max_retries: int,
) -> VectorDocument:
    """Generates a scene and persists it as a VectorDocument + VectorObjects — the exact
    generate-then-persist logic `POST /vector/documents` uses, extracted here so
    creative_service's brand-aware generation can call the same function instead of
    duplicating it. Raises VectorGenerationError exactly like generate_scene does; the
    caller is responsible for turning that into an HTTP response."""
    object_creates = await generate_scene(llm_client, model, prompt, max_objects, max_retries, purpose)

    document = VectorDocument(
        user_id=user_id,
        title=prompt[:255],
        purpose=purpose,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    db.add(document)
    db.flush()

    for oc in object_creates:
        db.add(
            VectorObject(
                document_id=document.id,
                object_type=oc.props.object_type,
                z_index=oc.z_index,
                layer_name=oc.layer_name,
                props=oc.props.model_dump(),
            )
        )
    db.commit()
    db.refresh(document)
    return document


def _resolve_operation(op_input, objects: list[VectorObject]) -> VectorOperation | None:
    if isinstance(op_input, AddObjectOpInput):
        return AddObjectOp(object=op_input.object)

    index = op_input.object_index
    if index < 0 or index >= len(objects):
        return None
    object_id = objects[index].id

    if isinstance(op_input, SetPropOpInput):
        return SetPropOp(object_id=object_id, prop=op_input.prop, value=op_input.value)
    if isinstance(op_input, DeleteObjectOpInput):
        return DeleteObjectOp(object_id=object_id)
    if isinstance(op_input, ReorderOpInput):
        return ReorderOp(object_id=object_id, z_index=op_input.z_index)
    raise AssertionError("unreachable")


async def generate_edit_operation(
    llm_client, model: str, objects: list[VectorObject], instruction: str, max_retries: int
) -> VectorOperation:
    messages = [
        {"role": "system", "content": _EDIT_SYSTEM_PROMPT.format(object_list=_describe_objects(objects))},
        {"role": "user", "content": instruction},
    ]

    last_error: str | None = None
    op_adapter = TypeAdapter(VectorOperationInput)
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```vector-op block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _OP_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```vector-op fenced block found"
            continue
        try:
            op_input = op_adapter.validate_python(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        resolved = _resolve_operation(op_input, objects)
        if resolved is None:
            last_error = "object_index is out of range for the current scene"
            continue
        return resolved

    raise VectorGenerationError(
        f"The model could not produce a valid edit after {max_retries + 1} attempt(s): {last_error}"
    )


_ALLOWED_PROPS_BY_TYPE: dict[str, set[str]] = {
    "RECT": {"x", "y", "width", "height", "rx", "fill", "stroke", "stroke_width", "opacity"},
    "CIRCLE": {"cx", "cy", "r", "fill", "stroke", "stroke_width", "opacity"},
    "ELLIPSE": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke_width", "opacity"},
    "LINE": {"x1", "y1", "x2", "y2", "stroke", "stroke_width", "opacity"},
    "POLYGON": {"points", "fill", "stroke", "stroke_width", "opacity"},
    "PATH": {"d", "fill", "stroke", "stroke_width", "opacity"},
    "TEXT": {"x", "y", "content", "font_size", "fill"},
}


def apply_operation(db: Session, document: VectorDocument, op: VectorOperation) -> VectorObject | None:
    """The single source of truth for mutating a document — used by both the AI-edit endpoint
    and the manual object endpoints, so an AI-driven edit and a manual property-panel edit are
    provably the same mutation path, not two divergent mechanisms."""
    if isinstance(op, AddObjectOp):
        obj = VectorObject(
            document_id=document.id,
            object_type=op.object.props.object_type,
            z_index=op.object.z_index,
            layer_name=op.object.layer_name,
            props=op.object.props.model_dump(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    obj = db.get(VectorObject, op.object_id)
    if obj is None or obj.document_id != document.id:
        raise ValueError("Object not found in this document.")

    if isinstance(op, DeleteObjectOp):
        db.delete(obj)
        db.commit()
        return None

    if isinstance(op, ReorderOp):
        obj.z_index = op.z_index
        db.commit()
        db.refresh(obj)
        return obj

    if isinstance(op, SetPropOp):
        value = validate_prop_value(obj.object_type, op.prop, op.value)
        new_props = dict(obj.props)
        new_props[op.prop] = value
        obj.props = new_props  # reassigned (not mutated in place) so SQLAlchemy detects the change
        db.commit()
        db.refresh(obj)
        return obj

    raise AssertionError("unreachable")


def validate_prop_value(object_type: str, prop: str, value: float | str) -> float | str:
    """The actual boundary for any prop mutation, generation-time or manual: is `prop` even
    valid for this object type, and is `value` an acceptable value for it. Shared by
    apply_operation's SET_PROP handling and animation_service's keyframe validation — one
    validation boundary, not two."""
    allowed = _ALLOWED_PROPS_BY_TYPE.get(object_type, set())
    if prop not in allowed:
        raise ValueError(f"'{prop}' is not a valid property for a {object_type}.")

    if prop in ("fill", "stroke"):
        return _validate_color(str(value))
    if prop == "opacity":
        result = float(value)
        if not 0.0 <= result <= 1.0:
            raise ValueError("opacity must be between 0 and 1.")
        return result
    if prop == "d":
        result_str = str(value)
        if not _PATH_DATA_RE.match(result_str):
            raise ValueError("Path data contains characters outside the allowed path-command set.")
        return result_str
    if prop == "content":
        return str(value)
    if prop == "points":
        raise ValueError("Editing 'points' via SET_PROP is not supported; delete and re-add the object.")
    return float(value)


def _style_attrs(props: dict) -> str:
    return (
        f'fill="{saxutils.escape(str(props.get("fill", "black")))}" '
        f'stroke="{saxutils.escape(str(props.get("stroke", "none")))}" '
        f'stroke-width="{props.get("stroke_width", 1.0)}" '
        f'opacity="{props.get("opacity", 1.0)}"'
    )


def _render_object(obj: VectorObject, element_id: str | None = None, extra_attrs: str = "") -> str:
    p = obj.props
    style = _style_attrs(p)
    # element_id/extra_attrs are only ever caller-constructed (e.g. f"obj-{uuid}", a CSS
    # animation shorthand built from already-validated fields), never user/LLM text — but
    # escaped anyway since they become attribute values like everything else here. Both are
    # empty by default, so Vector's own render_svg output is byte-identical to before.
    id_attr = f'id="{saxutils.escape(element_id)}" ' if element_id else ""
    extra = f" {extra_attrs}" if extra_attrs else ""
    t = obj.object_type
    if t == "RECT":
        return f'<rect {id_attr}x="{p["x"]}" y="{p["y"]}" width="{p["width"]}" height="{p["height"]}" rx="{p.get("rx", 0)}" {style}{extra}/>'
    if t == "CIRCLE":
        return f'<circle {id_attr}cx="{p["cx"]}" cy="{p["cy"]}" r="{p["r"]}" {style}{extra}/>'
    if t == "ELLIPSE":
        return f'<ellipse {id_attr}cx="{p["cx"]}" cy="{p["cy"]}" rx="{p["rx"]}" ry="{p["ry"]}" {style}{extra}/>'
    if t == "LINE":
        return f'<line {id_attr}x1="{p["x1"]}" y1="{p["y1"]}" x2="{p["x2"]}" y2="{p["y2"]}" {style}{extra}/>'
    if t == "POLYGON":
        points_str = " ".join(f"{x},{y}" for x, y in p["points"])
        return f'<polygon {id_attr}points="{points_str}" {style}{extra}/>'
    if t == "PATH":
        return f'<path {id_attr}d="{p["d"]}" {style}{extra}/>'
    if t == "TEXT":
        return (
            f'<text {id_attr}x="{p["x"]}" y="{p["y"]}" font-size="{p.get("font_size", 16)}" {style}{extra}>'
            f'{saxutils.escape(str(p["content"]))}</text>'
        )
    raise ValueError(f"Unknown object_type: {t}")  # pragma: no cover - object_type is validated at write time


def render_svg(document: VectorDocument, objects: list[VectorObject]) -> str:
    """The one and only place <svg>/<rect>/etc. markup strings are assembled, from already-
    validated VectorObject rows only — never from raw LLM text. This is what makes the whole
    pipeline safe without a general-purpose SVG sanitizer: the LLM never gets a text channel
    into the output, only a constrained JSON scene this function alone turns into markup."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{document.canvas_width}" '
        f'height="{document.canvas_height}" viewBox="0 0 {document.canvas_width} {document.canvas_height}">'
    ]
    if document.background_color:
        color = saxutils.escape(document.background_color)
        parts.append(
            f'<rect x="0" y="0" width="{document.canvas_width}" height="{document.canvas_height}" fill="{color}"/>'
        )
    for obj in sorted(objects, key=lambda o: o.z_index):
        parts.append(_render_object(obj))
    parts.append("</svg>")
    return "".join(parts)
