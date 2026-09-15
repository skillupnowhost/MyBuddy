"""MyBuddy Director (video/CG/VFX spec §5-6): idea -> script, the first stage of the
Story -> Video pipeline. Plain prose generation — no structured JSON needed here, since
storyboard_service.generate_storyboard already turns free-text prose into shots."""

_SYSTEM_PROMPT = """You are a screenwriter. Write a short film script based on the user's \
idea: 3-6 short scenes, each describing setting, action, and any dialogue in plain prose \
(no screenplay slugline formatting needed). Keep the whole script concise enough to board \
in under {max_shots} shots. Respond with ONLY the script text, no preamble or commentary."""


async def generate_script(llm_client, model: str, idea: str, max_shots: int) -> str:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(max_shots=max_shots)},
        {"role": "user", "content": idea},
    ]
    return await llm_client.chat(model, messages)
