import json
import re
import xml.sax.saxutils as saxutils

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.db.models.animation_document import AnimationDocument
from app.db.models.animation_keyframe import AnimationKeyframe
from app.db.models.vector_document import VectorDocument
from app.db.models.vector_object import VectorObject
from app.schemas.animation import AnimationKeyframeCreate, AnimationKeyframeInput
from app.services.vector_service import (
    VectorGenerationError,
    _ALLOWED_PROPS_BY_TYPE,
    _describe_objects,
    _render_object,
    validate_prop_value,
)

# v1 scope limit: path/polygon/text-content animation needs unequal-length interpolation or
# isn't a standard CSS animation target at all — excluded here, still settable via Vector's
# static SET_PROP edit.
_NON_ANIMATABLE_PROPS = {"d", "points", "content"}
_ANIMATABLE_PROPS_BY_TYPE: dict[str, set[str]] = {
    object_type: props - _NON_ANIMATABLE_PROPS for object_type, props in _ALLOWED_PROPS_BY_TYPE.items()
}

_KEYFRAMES_BLOCK_RE = re.compile(r"```animation-keyframes\s*\n(.*?)\n```", re.DOTALL)

_KEYFRAMES_SYSTEM_PROMPT = """You are an animation planner. Here is the scene you're animating, \
as a numbered list of objects:
{object_list}

The animation lasts {duration_ms}ms, from time 0 to {duration_ms}. Given a description of the \
motion, respond with ONLY a fenced block in exactly this format (no other text):
```animation-keyframes
{{"keyframes": [{{"object_index": 0, "time_ms": 0, "prop": "cx", "value": 50, "easing": "LINEAR"}}, \
{{"object_index": 0, "time_ms": {duration_ms}, "prop": "cx", "value": 300, "easing": "EASE_IN_OUT"}}]}}
```
Each keyframe sets one object's one property at one point in time; the browser interpolates \
between keyframes with the same object_index+prop automatically. object_index refers to the \
position in the numbered list above. easing must be one of LINEAR, EASE_IN, EASE_OUT, \
EASE_IN_OUT. Only animate properties that make sense to move/fade/recolor over time (position, \
size, fill, stroke, opacity) — do not attempt to animate path data, polygon points, or text \
content. Use at most {max_keyframes} keyframes."""


class _KeyframesResponse(BaseModel):
    keyframes: list[AnimationKeyframeInput]


def _resolve_keyframe(kf: AnimationKeyframeInput, objects: list[VectorObject]) -> AnimationKeyframeCreate | None:
    if kf.object_index < 0 or kf.object_index >= len(objects):
        return None
    obj = objects[kf.object_index]
    if kf.prop not in _ANIMATABLE_PROPS_BY_TYPE.get(obj.object_type, set()):
        return None
    return AnimationKeyframeCreate(
        object_id=obj.id, time_ms=kf.time_ms, prop=kf.prop, value=kf.value, easing=kf.easing
    )


async def generate_keyframes(
    llm_client, model: str, objects: list[VectorObject], prompt: str, duration_ms: int, max_keyframes: int, max_retries: int
) -> list[AnimationKeyframeCreate]:
    system_prompt = _KEYFRAMES_SYSTEM_PROMPT.format(
        object_list=_describe_objects(objects), duration_ms=duration_ms, max_keyframes=max_keyframes
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    last_error: str | None = None
    kf_adapter = TypeAdapter(_KeyframesResponse)
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```animation-keyframes block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _KEYFRAMES_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```animation-keyframes fenced block found"
            continue
        try:
            parsed = kf_adapter.validate_python(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        if len(parsed.keyframes) > max_keyframes:
            last_error = f"too many keyframes ({len(parsed.keyframes)} > {max_keyframes})"
            continue
        if not all(0 <= kf.time_ms <= duration_ms for kf in parsed.keyframes):
            last_error = f"keyframe time_ms must be between 0 and {duration_ms}"
            continue

        resolved: list[AnimationKeyframeCreate] = []
        ok = True
        for kf in parsed.keyframes:
            result = _resolve_keyframe(kf, objects)
            if result is None:
                last_error = f"object_index {kf.object_index} out of range or '{kf.prop}' isn't animatable for it"
                ok = False
                break
            try:
                result.value = validate_prop_value(objects[kf.object_index].object_type, kf.prop, kf.value)
            except ValueError as exc:
                last_error = str(exc)
                ok = False
                break
            resolved.append(result)
        if not ok:
            continue

        return resolved

    raise VectorGenerationError(
        f"The model could not produce valid keyframes after {max_retries + 1} attempt(s): {last_error}"
    )


_EASING_CSS = {
    "LINEAR": "linear",
    "EASE_IN": "ease-in",
    "EASE_OUT": "ease-out",
    "EASE_IN_OUT": "ease-in-out",
}

# CSS property names for the animatable props that differ from their SVG attribute spelling.
_CSS_PROP_NAMES = {"stroke_width": "stroke-width"}


def render_animation_svg(
    document: VectorDocument,
    objects: list[VectorObject],
    animation: AnimationDocument,
    keyframes: list[AnimationKeyframe],
) -> str:
    """Reuses vector_service._render_object directly rather than duplicating SVG-emission
    code — one place that must stay "restricted by construction" safe, not two. Keyframe
    values were already validated via validate_prop_value before being stored, same boundary
    as VectorObject.props."""
    by_object: dict[str, list[AnimationKeyframe]] = {}
    for kf in keyframes:
        by_object.setdefault(str(kf.object_id), []).append(kf)

    style_rules = []
    body_parts = []
    for obj in sorted(objects, key=lambda o: o.z_index):
        obj_keyframes = by_object.get(str(obj.id))
        if not obj_keyframes:
            body_parts.append(_render_object(obj))
            continue

        element_id = f"obj-{obj.id}"
        stops: dict[int, list[tuple[str, float | str]]] = {}
        for kf in sorted(obj_keyframes, key=lambda k: k.time_ms):
            pct = round(min(max(kf.time_ms / animation.duration_ms, 0.0), 1.0) * 100, 3) if animation.duration_ms else 0
            css_prop = _CSS_PROP_NAMES.get(kf.prop, kf.prop)
            stops.setdefault(pct, []).append((css_prop, kf.value))

        rule_lines = [f"@keyframes {element_id} {{"]
        for pct in sorted(stops):
            decls = "; ".join(f"{prop}: {value}" for prop, value in stops[pct])
            rule_lines.append(f"  {pct}% {{ {decls}; }}")
        rule_lines.append("}")
        style_rules.append("\n".join(rule_lines))

        easing = _EASING_CSS.get(obj_keyframes[0].easing, "linear")
        iteration = "infinite" if animation.loop else "1"
        anim_style = f"animation: {element_id} {animation.duration_ms}ms {easing} {iteration};"
        body_parts.append(
            _render_object(obj, element_id=element_id, extra_attrs=f'style="{anim_style}"')
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{document.canvas_width}" '
        f'height="{document.canvas_height}" viewBox="0 0 {document.canvas_width} {document.canvas_height}">'
    ]
    if style_rules:
        parts.append(f"<style>{' '.join(style_rules)}</style>")
    if document.background_color:
        color = saxutils.escape(document.background_color)
        parts.append(
            f'<rect x="0" y="0" width="{document.canvas_width}" height="{document.canvas_height}" fill="{color}"/>'
        )
    parts.extend(body_parts)
    parts.append("</svg>")
    return "".join(parts)
