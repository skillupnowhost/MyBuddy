from dataclasses import dataclass

from app.db.models.animation_keyframe import AnimationKeyframe
from app.db.models.motion_clip import MotionClip
from app.db.models.motion_project import MotionProject
from app.db.models.vector_document import VectorDocument
from app.db.models.vector_object import VectorObject
from app.services.animation_service import _CSS_PROP_NAMES, _EASING_CSS
from app.services.vector_service import _render_object


@dataclass
class ClipRenderData:
    clip: MotionClip
    vector_document: VectorDocument
    objects: list[VectorObject]
    keyframes: list[AnimationKeyframe]


def _prop_stops_for_object(
    clip: MotionClip, obj_keyframes: list[AnimationKeyframe], total_duration_ms: int
) -> dict[str, list[tuple[float, float | str]]]:
    """Groups this object's keyframes by CSS property, re-expressed as a percentage of the
    *project's* total duration (shifted by the clip's start offset), then synthesizes an
    explicit 0%/100% "hold" stop per property when the clip doesn't span the full project
    timeline — without this, a clip occupying only the middle of a longer composition would
    rely on implicit (and, across multiple composed clips, unreliable) CSS keyframe-range
    behavior instead of deterministically holding its first/last value."""
    by_prop: dict[str, list[tuple[float, float | str]]] = {}
    for kf in obj_keyframes:
        pct = 0.0 if not total_duration_ms else round(
            min(max((clip.start_offset_ms + kf.time_ms) / total_duration_ms, 0.0), 1.0) * 100, 3
        )
        css_prop = _CSS_PROP_NAMES.get(kf.prop, kf.prop)
        by_prop.setdefault(css_prop, []).append((pct, kf.value))

    for prop, stops in by_prop.items():
        stops.sort(key=lambda s: s[0])
        if stops[0][0] > 0:
            stops.insert(0, (0.0, stops[0][1]))
        if stops[-1][0] < 100:
            stops.append((100.0, stops[-1][1]))
    return by_prop


def render_motion_svg(project: MotionProject, clip_data: list[ClipRenderData]) -> str:
    """Reuses vector_service._render_object directly (via animation_service's easing/prop-name
    tables) rather than duplicating SVG-emission code — one place that emits <tag>s across
    Vector, Animator, and Motion, not three. This function's own job is purely timing/
    compositing: re-expressing each clip's local keyframe times against the project's shared
    timeline and positioning each clip's objects with a translate transform."""
    style_rules = []
    body_parts = []

    for data in sorted(clip_data, key=lambda d: d.clip.z_index):
        clip = data.clip
        by_object: dict[str, list[AnimationKeyframe]] = {}
        for kf in data.keyframes:
            by_object.setdefault(str(kf.object_id), []).append(kf)

        clip_body = []
        for obj in sorted(data.objects, key=lambda o: o.z_index):
            obj_keyframes = by_object.get(str(obj.id))
            element_id = f"clip-{clip.id}-obj-{obj.id}"
            if not obj_keyframes:
                clip_body.append(_render_object(obj))
                continue

            prop_stops = _prop_stops_for_object(clip, obj_keyframes, project.total_duration_ms)

            stops_by_pct: dict[float, list[tuple[str, float | str]]] = {}
            for prop, stops in prop_stops.items():
                for pct, value in stops:
                    stops_by_pct.setdefault(pct, []).append((prop, value))

            rule_lines = [f"@keyframes {element_id} {{"]
            for pct in sorted(stops_by_pct):
                decls = "; ".join(f"{prop}: {value}" for prop, value in stops_by_pct[pct])
                rule_lines.append(f"  {pct}% {{ {decls}; }}")
            rule_lines.append("}")
            style_rules.append("\n".join(rule_lines))

            easing = _EASING_CSS.get(obj_keyframes[0].easing, "linear")
            iteration = "infinite" if project.loop else "1"
            anim_style = f"animation: {element_id} {project.total_duration_ms}ms {easing} {iteration};"
            clip_body.append(_render_object(obj, element_id=element_id, extra_attrs=f'style="{anim_style}"'))

        body_parts.append(f'<g transform="translate({clip.x_offset},{clip.y_offset})">{"".join(clip_body)}</g>')

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{project.canvas_width}" '
        f'height="{project.canvas_height}" viewBox="0 0 {project.canvas_width} {project.canvas_height}">'
    ]
    if style_rules:
        parts.append(f"<style>{' '.join(style_rules)}</style>")
    parts.extend(body_parts)
    parts.append("</svg>")
    return "".join(parts)
