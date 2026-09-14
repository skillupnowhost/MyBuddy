import os
import uuid

from app.core.config import get_settings

settings = get_settings()

_SAFE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _save(user_id: str, subdir: str, extension: str, content: bytes) -> str:
    user_dir = os.path.join(settings.storage_dir, subdir, user_id)
    os.makedirs(user_dir, exist_ok=True)
    storage_path = os.path.join(user_dir, f"{uuid.uuid4().hex}{extension}")
    with open(storage_path, "wb") as f:
        f.write(content)
    return storage_path


def save_upload(user_id: str, content_type: str, content: bytes) -> str:
    """Saves a document upload under a randomized filename, namespaced by user, outside any
    web-served/executable path. Never trusts the client-supplied filename for the disk path."""
    extension = _SAFE_EXTENSIONS.get(content_type, "")
    return _save(user_id, "documents", extension, content)


def save_dataset(user_id: str, content: bytes) -> str:
    """Saves a training dataset upload (always .jsonl), same isolation rules as save_upload."""
    return _save(user_id, "datasets", ".jsonl", content)


def delete_upload(storage_path: str) -> None:
    try:
        os.remove(storage_path)
    except OSError:
        pass
