from dataclasses import dataclass

from app.services.chunking import _split_text


@dataclass
class CodeChunkPiece:
    content: str
    chunk_index: int
    start_line: int
    end_line: int


def chunk_code_file(content: str, size: int, overlap: int) -> list[CodeChunkPiece]:
    """Splits a source file using the same blank-line/space-boundary heuristic as document
    chunking (blank lines are already a reasonable proxy for top-level function/class
    boundaries in most languages), tracking a line range instead of a page number. No
    per-language AST parsing in v1 — that would need a grammar/parser per language for a
    marginal quality gain over this, which is already generic over any text."""
    pieces = []
    for index, piece_text in enumerate(_split_text(content, size, overlap)):
        offset = content.find(piece_text)
        offset = offset if offset != -1 else 0
        start_line = content.count("\n", 0, offset) + 1
        end_line = start_line + piece_text.count("\n")
        pieces.append(
            CodeChunkPiece(content=piece_text, chunk_index=index, start_line=start_line, end_line=end_line)
        )
    return pieces
