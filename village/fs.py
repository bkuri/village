"""Shared file system utilities."""

import json
from pathlib import Path
from typing import Any


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file atomically using temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temp_path.write_text(content, encoding=encoding)
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def read_json(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    """Read and parse a JSON file."""
    data: dict[str, Any] = json.loads(path.read_text(encoding=encoding))
    return data


def write_json(path: Path, data: Any, indent: int = 2, sort_keys: bool = True, encoding: str = "utf-8") -> None:
    """Write JSON data to file atomically."""
    atomic_write(path, json.dumps(data, indent=indent, sort_keys=sort_keys), encoding=encoding)


def ensure_parent(path: Path) -> None:
    """Ensure parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
