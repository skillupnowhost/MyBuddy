from dataclasses import dataclass

from app.services.document_loaders.base import ExtractedPage


@dataclass
class Chunk:
    content: str
    chunk_index: int
    page_number: int | None


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """Splits on paragraph boundaries where possible, falling back to a fixed-size
    sliding window with overlap so no chunk silently exceeds `size`."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start, end)
            if boundary == -1 or boundary <= start:
                boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages: list[ExtractedPage], size: int, overlap: int) -> list[Chunk]:
    chunks = []
    index = 0
    for page in pages:
        for piece in _split_text(page.text, size, overlap):
            chunks.append(Chunk(content=piece, chunk_index=index, page_number=page.page_number))
            index += 1
    return chunks
