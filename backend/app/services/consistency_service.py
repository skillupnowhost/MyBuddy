"""Consistency guidance for CharacterIdentitySystem + WorldBible (video/CG/VFX spec §8-9).
Same mechanism as creative_service.brand_guidance: a short paragraph prepended to a
generation prompt, no new LLM protocol or generation pathway. This is the entire consistency
story for this project — see character.py's docstring for why a real cross-shot visual-
consistency ML system (LoRA/embeddings/face-matching) is out of scope here."""
from app.db.models.character import Character
from app.db.models.world_bible import WorldBible


def character_guidance(characters: list[Character]) -> str:
    if not characters:
        return ""

    parts = []
    for character in characters:
        detail_bits = []
        if character.appearance:
            detail_bits.append(character.appearance)
        if character.personality:
            detail_bits.append(f"personality: {character.personality}")
        details = "; ".join(detail_bits)
        parts.append(f"{character.name} ({details})" if details else character.name)

    characters_block = "; ".join(parts)
    return f"Characters in this story, keep their appearance and personality consistent across shots: {characters_block}."


def world_guidance(world_bible: WorldBible | None) -> str:
    if world_bible is None:
        return ""

    parts = []
    if world_bible.setting_description:
        parts.append(f"Setting: {world_bible.setting_description}.")
    if world_bible.atmosphere:
        parts.append(f"Atmosphere: {world_bible.atmosphere}.")
    if world_bible.visual_style:
        parts.append(f"Visual style: {world_bible.visual_style}.")
    if world_bible.color_palette:
        parts.append(f"Color palette: {world_bible.color_palette}.")
    if world_bible.rules:
        parts.append(f"World rules: {world_bible.rules}.")

    return " ".join(parts)
