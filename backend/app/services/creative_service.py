from app.db.models.brand_kit import BrandKit


def brand_guidance(brand_kit: BrandKit | None) -> str:
    """The entire Creative Director orchestration mechanism: a short paragraph prepended to
    whatever prompt the user gives before calling vector_service.create_document_from_scene
    — no new LLM protocol, no new generation pathway. Empty string if no brand kit is set."""
    if brand_kit is None:
        return ""

    parts = []
    colors = []
    if brand_kit.primary_color:
        colors.append(f"primary color {brand_kit.primary_color}")
    if brand_kit.secondary_color:
        colors.append(f"secondary color {brand_kit.secondary_color}")
    if brand_kit.accent_color:
        colors.append(f"accent color {brand_kit.accent_color}")
    if colors:
        parts.append(f"Use this brand's identity: {', '.join(colors)}.")
    if brand_kit.font_family:
        parts.append(f"(Preferred font: {brand_kit.font_family}, for stylistic reference only.)")

    return " ".join(parts)
