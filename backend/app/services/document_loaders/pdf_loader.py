from pypdf import PdfReader

from app.services.document_loaders.base import DocumentLoader, ExtractedPage


class PDFLoader(DocumentLoader):
    """Loads PDF files, preserving page numbers for source attribution."""

    def extract(self, file_path: str) -> list[ExtractedPage]:
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(ExtractedPage(text=text, page_number=i + 1))
        return pages
