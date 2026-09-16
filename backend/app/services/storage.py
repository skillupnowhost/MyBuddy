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

_SAFE_IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_SAFE_VIDEO_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


def _save(user_id: str, subdir: str, extension: str, content: bytes) -> str:
    # storage_dir defaults to a relative "./data" — must be made absolute here, since the
    # resulting storage_path is persisted to the DB and later read back by other, independent
    # processes (imagegen/video/training subprocesses) with their own working directory. A
    # relative path stored by this process would silently resolve to the wrong file under
    # theirs (see edit_image.py's fetch_image, which reads this column verbatim).
    user_dir = os.path.join(os.path.abspath(settings.storage_dir), subdir, user_id)
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


def save_image(user_id: str, content_type: str, content: bytes) -> str:
    """Saves an uploaded image, same isolation rules as save_upload."""
    extension = _SAFE_IMAGE_EXTENSIONS.get(content_type, "")
    return _save(user_id, "images", extension, content)


def save_video(user_id: str, content_type: str, content: bytes) -> str:
    """Saves an uploaded video, same isolation rules as save_upload. Stored under
    'videos/<user_id>' — the same subdir the video-generation subprocess writes generated
    output to (see video/scripts/generate.py:save_generated_video), so uploaded and
    generated videos are indistinguishable in storage layout, only in how the `videos` row
    was created."""
    extension = _SAFE_VIDEO_EXTENSIONS.get(content_type, "")
    return _save(user_id, "videos", extension, content)


def delete_upload(storage_path: str) -> None:
    try:
        os.remove(storage_path)
    except OSError:
        pass
