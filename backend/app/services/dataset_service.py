import json

from app.db.models.dataset import Dataset

REQUIRED_ROLES = {"user", "assistant"}


def validate_dataset_file(storage_path: str) -> tuple[bool, int, str | None]:
    """Validates a JSONL instruction dataset: each line must be
    {"messages": [{"role": "user"|"assistant"|"system", "content": "..."}, ...]}
    with at least one user and one assistant turn. Returns (is_valid, num_examples, error)."""
    count = 0
    try:
        with open(storage_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    example = json.loads(line)
                except json.JSONDecodeError:
                    return False, count, f"Line {line_num}: not valid JSON"

                if "messages" not in example or not isinstance(example["messages"], list):
                    return False, count, f"Line {line_num}: missing 'messages' array"

                roles_seen = set()
                for msg in example["messages"]:
                    if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                        return False, count, f"Line {line_num}: each message needs 'role' and 'content'"
                    if not isinstance(msg["content"], str) or not msg["content"].strip():
                        return False, count, f"Line {line_num}: message content must be non-empty text"
                    roles_seen.add(msg["role"])

                if not REQUIRED_ROLES.issubset(roles_seen):
                    return False, count, f"Line {line_num}: needs at least one 'user' and one 'assistant' message"

                count += 1
    except OSError as exc:
        return False, 0, f"Could not read dataset file: {exc}"

    if count == 0:
        return False, 0, "Dataset is empty"

    return True, count, None


def apply_validation_result(dataset: Dataset) -> None:
    is_valid, count, error = validate_dataset_file(dataset.storage_path)
    dataset.num_examples = count
    dataset.status = "VALIDATED" if is_valid else "INVALID"
    dataset.error_message = error
