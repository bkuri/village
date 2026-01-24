"""Context file management (JSON parsing, writing)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from village.chat.schema import ALLOWED_FILES

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object


@dataclass
class ContextUpdate:
    """Parsed context update from LLM response."""

    writes: dict[str, str]
    notes: list[str]
    open_questions: list[str]
    error: Optional[str] = None


@dataclass
class ContextFile:
    """Context file on disk."""

    name: str
    path: Path
    content: str


def get_context_dir(config: _Config) -> Path:
    """
    Get context directory path (create if missing).

    Args:
        config: Village config object

    Returns:
        Path to .village/context/
    """
    context_dir = config.village_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir


def write_context_file(context_dir: Path, filename: str, content: str) -> Path:
    """
    Write context file to disk (incremental update).

    Args:
        context_dir: Path to .village/context/
        filename: File name (e.g., "project.md")
        content: Markdown content

    Returns:
        Path to written file
    """
    if filename not in ALLOWED_FILES:
        raise ValueError(f"Invalid context file name: {filename}")

    file_path = context_dir / filename
    file_path.write_text(content, encoding="utf-8")
    logger.debug(f"Wrote context file: {file_path}")
    return file_path


def get_current_context(context_dir: Path) -> dict[str, ContextFile]:
    """
    Read all existing context files from disk.

    Args:
        context_dir: Path to .village/context/

    Returns:
        Dict mapping filename -> ContextFile (only for existing files)
    """
    context_files = {}

    for filename in ALLOWED_FILES:
        file_path = context_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            context_files[filename] = ContextFile(name=filename, path=file_path, content=content)

    return context_files


def apply_context_update(context_dir: Path, update: ContextUpdate) -> dict[str, Path]:
    """
    Apply context update to disk (write updated files).

    Args:
        context_dir: Path to .village/context/
        update: Parsed ContextUpdate from LLM

    Returns:
        Dict mapping filename -> written Path

    Raises:
        ValueError: If update contains invalid filenames
    """
    written_files = {}

    for filename, content in update.writes.items():
        file_path = write_context_file(context_dir, filename, content)
        written_files[filename] = file_path

    return written_files
