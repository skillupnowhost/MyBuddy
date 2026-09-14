import docx

from app.services.document_loaders.base import DocumentLoader, ExtractedPage


class DocxLoader(DocumentLoader):
    """Loads .docx files. DOCX has no fixed pagination, so page_number is always None."""

    def extract(self, file_path: str) -> list[ExtractedPage]:
        doc = docx.Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [ExtractedPage(text=text, page_number=None)]
