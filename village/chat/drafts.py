"""Draft task storage for task creation workflow."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object

logger = logging.getLogger(__name__)


@dataclass
class DraftTask:
    """Draft task manifest stored in .village/drafts/."""

    id: str
    created_at: datetime
    title: str
    description: str
    scope: str  # feature|fix|investigation|refactoring
    relates_to_goals: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    estimate: str = "unknown"  # hours|days|weeks|unknown
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    llm_notes: list[str] = field(default_factory=list)


def _get_drafts_dir(config: _Config) -> Path:
    """
    Get drafts directory path.

    Args:
        config: Village config

    Returns:
        Path to .village/drafts/
    """
    drafts_dir = config.village_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    return drafts_dir


def save_draft(draft: DraftTask, config: _Config) -> Path:
    """
    Save draft task to disk.

    Args:
        draft: DraftTask to save
        config: Village config

    Returns:
        Path to saved draft file
    """
    drafts_dir = _get_drafts_dir(config)
    file_path = drafts_dir / f"{draft.id}.json"

    draft_dict = asdict(draft)
    # Convert datetime to ISO string for JSON serialization
    draft_dict["created_at"] = draft.created_at.isoformat()

    file_path.write_text(json.dumps(draft_dict, indent=2), encoding="utf-8")
    logger.debug(f"Saved draft: {file_path}")

    return file_path


def load_draft(draft_id: str, config: _Config) -> DraftTask:
    """
    Load draft task from disk.

    Args:
        draft_id: Draft ID (e.g., "draft-abc123")
        config: Village config

    Returns:
        DraftTask object

    Raises:
        FileNotFoundError: If draft not found
        ValueError: If draft JSON is invalid
    """
    drafts_dir = _get_drafts_dir(config)
    file_path = drafts_dir / f"{draft_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Draft not found: {draft_id}")

    content = file_path.read_text(encoding="utf-8")
    draft_dict = json.loads(content)

    # Convert ISO string back to datetime
    draft_dict["created_at"] = datetime.fromisoformat(draft_dict["created_at"])

    draft = DraftTask(**draft_dict)
    logger.debug(f"Loaded draft: {file_path}")

    return draft


def list_drafts(config: _Config) -> list[DraftTask]:
    """
    List all draft tasks.

    Args:
        config: Village config

    Returns:
        List of DraftTask objects (sorted by created_at, newest first)
    """
    drafts_dir = _get_drafts_dir(config)
    drafts = []

    for file_path in drafts_dir.glob("draft-*.json"):
        try:
            draft = load_draft(file_path.stem, config)
            drafts.append(draft)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load draft {file_path}: {e}")

    # Sort by created_at descending (newest first)
    drafts.sort(key=lambda d: d.created_at, reverse=True)

    return drafts


def delete_draft(draft_id: str, config: _Config) -> None:
    """
    Delete draft task from disk.

    Args:
        draft_id: Draft ID to delete
        config: Village config

    Raises:
        FileNotFoundError: If draft not found
    """
    drafts_dir = _get_drafts_dir(config)
    file_path = drafts_dir / f"{draft_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Draft not found: {draft_id}")

    file_path.unlink()
    logger.debug(f"Deleted draft: {file_path}")


def generate_draft_id() -> str:
    """
    Generate a unique draft ID.

    Returns:
        Draft ID in format "draft-<8-char-uuid>"
    """
    unique_id = uuid4().hex[:8]
    return f"draft-{unique_id}"


def draft_id_to_task_id(draft_id: str) -> str:
    """
    Convert draft ID to Beads task ID.

    Example: df-a1b2c3 -> bd-a1b2c3

    Args:
        draft_id: Draft ID (format: df-<6-char-hex>)

    Returns:
        Task ID for use with bd create --id

    Raises:
        ValueError: If draft_id format is invalid
    """
    if not draft_id.startswith("df-"):
        raise ValueError(f"Invalid draft ID format: {draft_id}")

    hex_suffix = draft_id[3:]  # Extract 'a1b2c3' from 'df-a1b2c3'
    return f"bd-{hex_suffix}"
