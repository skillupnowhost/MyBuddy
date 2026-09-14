from abc import ABC, abstractmethod
from dataclasses import dataclass


class UnsupportedDocumentType(Exception):
    pass


@dataclass
class ExtractedPage:
    text: str
    page_number: int | None = None


class DocumentLoader(ABC):
    """Extracts plain text from a document. One implementation per file format.

    Deliberately separate from chunking: a loader's job is only to turn bytes on disk into
    (text, page_number) pairs — how that text gets split into chunks is a different concern.
    """

    @abstractmethod
    def extract(self, file_path: str) -> list[ExtractedPage]:
        ...
