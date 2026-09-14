from app.services.document_loaders.base import DocumentLoader, ExtractedPage, UnsupportedDocumentType
from app.services.document_loaders.docx_loader import DocxLoader
from app.services.document_loaders.pdf_loader import PDFLoader
from app.services.document_loaders.text_loader import TextLoader

_LOADERS_BY_CONTENT_TYPE: dict[str, DocumentLoader] = {
    "application/pdf": PDFLoader(),
    "text/plain": TextLoader(),
    "text/markdown": TextLoader(),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxLoader(),
}


def get_loader(content_type: str) -> DocumentLoader:
    loader = _LOADERS_BY_CONTENT_TYPE.get(content_type)
    if loader is None:
        raise UnsupportedDocumentType(f"No loader registered for content type: {content_type}")
    return loader


__all__ = ["DocumentLoader", "ExtractedPage", "UnsupportedDocumentType", "get_loader"]
