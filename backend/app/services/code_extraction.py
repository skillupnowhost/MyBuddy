import os
import zipfile
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()

_READ_CHUNK_BYTES = 64 * 1024

_LANGUAGE_BY_EXTENSION = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".java": "java", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".kt": "kotlin", ".swift": "swift", ".md": "markdown", ".txt": "text", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".sql": "sql", ".html": "html", ".css": "css",
}


class ZipValidationError(Exception):
    """Raised for anything that should abort the whole upload (bad zip, too many entries,
    cumulative size over the project cap) as opposed to a single bad entry, which is
    silently skipped instead."""


@dataclass
class ExtractedFile:
    relative_path: str
    storage_path: str
    size_bytes: int
    language: str | None


def _is_within_directory(directory: str, target: str) -> bool:
    directory = os.path.realpath(directory)
    target = os.path.realpath(target)
    return os.path.commonpath([directory]) == os.path.commonpath([directory, target])


def extract_code_zip(zip_path: str, dest_dir: str) -> list[ExtractedFile]:
    """Extracts source files from a zip into dest_dir with guards against path traversal
    and zip bombs.

    Per-entry problems (directories, excluded dirs like node_modules/.git, disallowed
    extensions, oversized files, entries that look like a zip bomb via their compression
    ratio, non-UTF-8/binary content, path-traversal filenames) are silently skipped rather
    than failing the whole upload. Cumulative resource-exhaustion signals (too many entries,
    total uncompressed size over the cap) abort the whole extraction by raising
    ZipValidationError — callers must then discard dest_dir.

    Destination paths are always rebuilt from sanitized path segments via os.path.join,
    never from the raw entry.filename — this is what makes traversal (`../../etc`) and
    Windows-drive-letter tricks (`C:/evil.py`) inert: both just become an oddly named
    subdirectory under dest_dir rather than an escape.
    """
    os.makedirs(dest_dir, exist_ok=True)
    extracted: list[ExtractedFile] = []
    total_bytes = 0

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise ZipValidationError("Uploaded file is not a valid zip archive.") from exc

    with zf:
        infolist = zf.infolist()
        if len(infolist) > settings.code_max_files_per_project:
            raise ZipValidationError(
                f"Zip contains more than {settings.code_max_files_per_project} entries."
            )

        for entry in infolist:
            if entry.is_dir():
                continue

            normalized = entry.filename.replace("\\", "/")
            parts = [p for p in normalized.split("/") if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts):
                continue  # empty or path-traversal entry - skip, never extract

            if any(p in settings.code_excluded_dir_names for p in parts[:-1]):
                continue

            extension = os.path.splitext(parts[-1])[1].lower()
            if extension not in settings.code_allowed_extensions:
                continue

            if entry.file_size > settings.code_max_file_size_bytes:
                continue
            if (
                entry.compress_size > 0
                and entry.file_size / entry.compress_size > settings.code_max_compression_ratio
            ):
                continue  # looks like a zip bomb - skip this entry

            if total_bytes + entry.file_size > settings.code_max_extracted_size_bytes:
                raise ZipValidationError(
                    "Extracted project would exceed the "
                    f"{settings.code_max_extracted_size_bytes // (1024 * 1024)}MB size limit."
                )

            relative_path = "/".join(parts)
            dest_path = os.path.normpath(os.path.join(dest_dir, *parts))
            if not _is_within_directory(dest_dir, dest_path):
                continue  # defense in depth, in addition to the ".." check above

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            written = 0
            aborted = False
            with zf.open(entry) as source, open(dest_path, "wb") as target:
                while True:
                    chunk = source.read(_READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > settings.code_max_file_size_bytes:
                        aborted = True  # entry lied about its declared size - stop reading it
                        break
                    target.write(chunk)
            if aborted:
                os.remove(dest_path)
                continue

            try:
                with open(dest_path, "r", encoding="utf-8") as f:
                    f.read()
            except (UnicodeDecodeError, OSError):
                os.remove(dest_path)
                continue  # treat undecodable content as binary, not source

            total_bytes += written
            extracted.append(
                ExtractedFile(
                    relative_path=relative_path,
                    storage_path=dest_path,
                    size_bytes=written,
                    language=_LANGUAGE_BY_EXTENSION.get(extension),
                )
            )

    return extracted
