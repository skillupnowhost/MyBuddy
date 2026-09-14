"""CameraPlanner (video/CG/VFX spec §10): turns a structured CameraPlan into a natural-
language description — the bridge between CameraPlan's structured fields and a text-prompt-
driven generator (Storyboard's generation_prompt, MyBuddy Video's prompt), the same role
consistency_service.character_guidance/world_guidance play for their inputs."""
from app.db.models.camera_plan import CameraPlan

_MOTION_DESCRIPTIONS = {
    "STATIC": "a static, locked-off shot",
    "PAN": "a panning shot",
    "TILT": "a tilting shot",
    "ZOOM_IN": "a shot that zooms in",
    "ZOOM_OUT": "a shot that zooms out",
    "DOLLY_IN": "a dolly-in shot",
    "DOLLY_OUT": "a dolly-out shot",
    "TRUCK_LEFT": "a shot that trucks left",
    "TRUCK_RIGHT": "a shot that trucks right",
    "ORBIT": "an orbiting shot circling the subject",
    "CRANE": "a crane shot",
    "HANDHELD": "a handheld shot",
    "DRONE": "an aerial drone shot",
    "TRACKING": "a tracking shot following the subject",
    "RACK_FOCUS": "a rack-focus shot shifting focus between subjects",
    "PUSH_IN": "a slow push-in shot",
    "PULL_OUT": "a slow pull-out shot",
    "ROTATE_360": "a 360-degree rotating shot",
    "FIRST_PERSON": "a first-person point-of-view shot",
    "THIRD_PERSON": "a third-person following shot",
}


def describe_camera_plan(plan: CameraPlan) -> str:
    parts = [_MOTION_DESCRIPTIONS.get(plan.motion_type, plan.motion_type.lower())]

    lens_bits = []
    if plan.lens:
        lens_bits.append(plan.lens)
    if plan.focal_length_mm:
        lens_bits.append(f"{plan.focal_length_mm:g}mm")
    if plan.aperture:
        lens_bits.append(f"f/{plan.aperture:g}")
    if lens_bits:
        parts.append(f"shot on {', '.join(lens_bits)}")

    if plan.shutter_speed:
        parts.append(f"shutter {plan.shutter_speed}")
    if plan.depth_of_field:
        parts.append(f"{plan.depth_of_field} depth of field")
    if plan.motion_path:
        parts.append(plan.motion_path)

    return ", ".join(parts)
