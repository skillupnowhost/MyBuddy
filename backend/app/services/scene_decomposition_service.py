"""AI 3D Scene Generator (video/CG/VFX spec §13), honestly scoped: Shap-E (see
model_3d_generation_service) generates one independent object at a time with no awareness of
position/scale relative to other objects — there is no real 3D scene-composition engine in
this project (that's MyBuddy CG's own §11-13 gap, not something this layer can paper over).
What this genuinely provides: decomposing a scene description into a list of individual
object prompts via the LLM (same fenced-block + Pydantic-validation + repair-retry
convention as storyboard_service), each of which can then be sent to MyBuddy CG as its own
text-to-3D generation job. The caller is responsible for actually arranging the resulting
meshes in a 3D tool afterward — this is a prompt-decomposition helper, not a scene placer."""
import json
import re

from pydantic import BaseModel, ValidationError

_SCENE_BLOCK_RE = re.compile(r"```scene-objects\s*\n(.*?)\n```", re.DOTALL)

_SYSTEM_PROMPT = """You are a 3D scene planner. Given a scene description, break it into a \
list of individual objects that would need to be modeled separately. Respond with ONLY a \
fenced block in exactly this format (no other text):
```scene-objects
{{"objects": [{{"label": "neon sign", "prompt": "a glowing pink neon sign, low-poly"}}]}}
```
Rules:
- Use at most {max_objects} objects. Cover the scene's key elements; skip minor background detail.
- "label" is a short human-readable name (2-4 words).
- "prompt" is a self-contained text-to-3D generation prompt for that one object alone (style, \
shape, and materials — no scene context, no other objects mentioned)."""


class SceneObject(BaseModel):
    label: str
    prompt: str


class _SceneObjectsResponse(BaseModel):
    objects: list[SceneObject]


class SceneDecompositionError(Exception):
    """Raised when the model can't be coaxed into a valid object list within the retry
    budget — the caller must surface this clearly, never fall back to an empty scene."""


async def decompose_scene(llm_client, model: str, description: str, max_objects: int, max_retries: int) -> list[SceneObject]:
    system_prompt = _SYSTEM_PROMPT.format(max_objects=max_objects)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": description},
    ]

    last_error: str | None = None
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```scene-objects block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _SCENE_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```scene-objects fenced block found"
            continue
        try:
            parsed = _SceneObjectsResponse.model_validate(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        if not parsed.objects:
            last_error = "objects must not be empty"
            continue
        if len(parsed.objects) > max_objects:
            last_error = f"too many objects ({len(parsed.objects)} > {max_objects})"
            continue

        return parsed.objects

    raise SceneDecompositionError(
        f"The model could not produce a valid scene breakdown after {max_retries + 1} attempt(s): {last_error}"
    )
