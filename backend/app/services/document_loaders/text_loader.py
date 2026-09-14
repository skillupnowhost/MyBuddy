from app.services.document_loaders.base import DocumentLoader, ExtractedPage


class TextLoader(DocumentLoader):
    """Loads plain text and Markdown files."""

    def extract(self, file_path: str) -> list[ExtractedPage]:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return [ExtractedPage(text=text, page_number=None)]
