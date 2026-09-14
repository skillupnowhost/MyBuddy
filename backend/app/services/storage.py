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


def save_upload(user_id: str, content_type: str, content: bytes) -> str:
    """Saves upload content under a randomized filename, namespaced by user, outside any
    web-served/executable path. Never trusts the client-supplied filename for the disk path."""
    user_dir = os.path.join(settings.storage_dir, user_id)
    os.makedirs(user_dir, exist_ok=True)

    extension = _SAFE_EXTENSIONS.get(content_type, "")
    storage_path = os.path.join(user_dir, f"{uuid.uuid4().hex}{extension}")

    with open(storage_path, "wb") as f:
        f.write(content)

    return storage_path


def delete_upload(storage_path: str) -> None:
    try:
        os.remove(storage_path)
    except OSError:
        pass
