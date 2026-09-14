"""StoryboardGenerator (video/CG/VFX spec §7): script -> shot-by-shot storyboard. Pure LLM
structured output — same fenced-block + Pydantic-validation + repair-retry convention as
vector_service.generate_scene, not a new pattern. No image/video model is involved here, so
(like Vector) this runs inline in the API process rather than as a subprocess."""
import json
import re

from pydantic import BaseModel, ValidationError

from app.schemas.storyboard import StoryboardShotCreate

_SHOT_LIST_BLOCK_RE = re.compile(r"```storyboard\s*\n(.*?)\n```", re.DOTALL)

_SYSTEM_PROMPT = """You are a film storyboard generator. Given a script, break it into an \
ordered list of shots. Respond with ONLY a fenced block in exactly this format (no other text):
```storyboard
{{"shots": [{{"scene_id": "1", "duration_seconds": 4.0, "camera": "medium shot, static", \
"lens": "50mm", "composition": "rule of thirds, subject left", "characters": ["Ava"], \
"action": "Ava opens the door and steps inside.", "environment": "dim apartment hallway", \
"lighting": "single overhead bulb, warm", "dialogue": null, "sound": "door creak", \
"vfx": null, "generation_prompt": "Ava opens a door and steps into a dim, warmly-lit \
apartment hallway, medium static shot, 50mm lens"}}]}}
```
Rules:
- Use at most {max_shots} shots. Cover the whole script; do not skip scenes.
- duration_seconds must be a positive number (typically 2-10 for a single shot).
- characters is a list of character names present in that shot (can be empty).
- dialogue/sound/vfx/lens/composition/lighting/scene_id may be null when not applicable.
- generation_prompt must be a single self-contained sentence describing the shot visually \
(camera + subject + action + environment + lighting) — this is what gets handed to an image \
or video generation model later, so it must make sense with no other context."""


class StoryboardGenerationError(Exception):
    """Raised when the model can't be coaxed into a valid shot list within the retry
    budget — the caller must surface this clearly, never fall back to an empty storyboard."""


class _ShotListResponse(BaseModel):
    shots: list[StoryboardShotCreate]


async def generate_storyboard(
    llm_client, model: str, script: str, max_shots: int, max_retries: int, guidance: str = ""
) -> list[StoryboardShotCreate]:
    """`guidance` is consistency guidance from character_service.character_guidance/
    world_guidance, appended to the system prompt — the same prompt-injection mechanism
    creative_service.brand_guidance uses for Vector, not a new protocol."""
    system_prompt = _SYSTEM_PROMPT.format(max_shots=max_shots)
    if guidance:
        system_prompt = f"{system_prompt}\n\n{guidance}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": script},
    ]

    last_error: str | None = None
    for _ in range(max_retries + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your last response was invalid: {last_error}. Reply again with "
                    "ONLY a corrected fenced ```storyboard block.",
                }
            )
        reply = await llm_client.chat(model, messages)
        messages.append({"role": "assistant", "content": reply})

        match = _SHOT_LIST_BLOCK_RE.search(reply)
        if not match:
            last_error = "no ```storyboard fenced block found"
            continue
        try:
            shot_list = _ShotListResponse.model_validate(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:500]
            continue

        if not shot_list.shots:
            last_error = "shots must not be empty"
            continue
        if len(shot_list.shots) > max_shots:
            last_error = f"too many shots ({len(shot_list.shots)} > {max_shots})"
            continue

        return shot_list.shots

    raise StoryboardGenerationError(
        f"The model could not produce a valid storyboard after {max_retries + 1} attempt(s): {last_error}"
    )
