"""Task ID generation with collision-safe bd-xxxx format."""

import json
import re
import secrets
from pathlib import Path

ID_PREFIX = "bd"
ID_LENGTH = 4
MAX_COLLISION_RETRIES = 100


def generate_task_id(existing_ids: set[str]) -> str:
    """Generate a unique task ID in bd-xxxx format.

    Uses cryptographically random hex characters. Collision-safe:
    retries with longer IDs if needed.

    Args:
        existing_ids: Set of already-used task IDs

    Returns:
        Unique task ID string (e.g. "bd-a3f8")
    """
    for _ in range(MAX_COLLISION_RETRIES):
        hex_part = secrets.token_hex(ID_LENGTH // 2)[:ID_LENGTH]
        task_id = f"{ID_PREFIX}-{hex_part}"
        if task_id not in existing_ids:
            return task_id

    for length in range(ID_LENGTH + 1, ID_LENGTH + 8):
        hex_part = secrets.token_hex(length // 2)[:length]
        task_id = f"{ID_PREFIX}-{hex_part}"
        if task_id not in existing_ids:
            return task_id

    raise RuntimeError(f"Failed to generate unique task ID after {MAX_COLLISION_RETRIES} retries")


def collect_existing_ids(tasks_file: Path) -> set[str]:
    """Read all task IDs from a JSONL tasks file.

    Args:
        tasks_file: Path to tasks.jsonl

    Returns:
        Set of task ID strings
    """
    if not tasks_file.exists():
        return set()

    ids: set[str] = set()
    for line in tasks_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            task_id = data.get("id", "")
            if task_id:
                ids.add(task_id)
        except (json.JSONDecodeError, KeyError):
            continue
    return ids


def validate_task_id(task_id: str) -> bool:
    return bool(re.match(rf"^{ID_PREFIX}-[a-f0-9]{{{ID_LENGTH},}}$", task_id.lower()))


def extract_task_id_from_output(output: str) -> str | None:
    patterns = [
        rf"({ID_PREFIX}-[a-z0-9]{{{ID_LENGTH},}})",
        rf"created:\s*({ID_PREFIX}-[a-z0-9]+)",
        rf"task\s+id:\s*({ID_PREFIX}-[a-z0-9]+)",
        rf"id:\s*({ID_PREFIX}-[a-z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None
