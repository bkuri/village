"""Session state management for Village Chat."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object

logger = logging.getLogger(__name__)


@dataclass
class SessionSnapshot:
    """Capture state for reset capability."""

    start_time: datetime
    batch_id: str
    initial_context_files: dict[str, str]
    current_context_files: dict[str, str]
    pending_enables: list[str]
    created_task_ids: list[str]


def save_session_state(state: Any, config: _Config) -> None:
    """Persist session state for polling/recovery."""
    session_file = config.village_dir / "session.json"

    session_data = {
        "mode": str(state.mode) if not isinstance(state.mode, str) else state.mode,
        "pending_enables": state.pending_enables,
        "context_diffs": state.context_diffs,
        "batch_submitted": state.batch_submitted,
        "updated_at": datetime.now().isoformat(),
    }

    session_file.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
    logger.debug(f"Saved session state: {session_file}")


def load_session_state(config: _Config) -> dict[str, Any]:
    """Load persisted session state (for polling/recovery)."""
    session_file = config.village_dir / "session.json"

    if not session_file.exists():
        return {}

    content = session_file.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(content)

    return data


def count_pending_changes(config: _Config) -> int:
    """Count pending enables + context diffs."""
    state = load_session_state(config)

    pending_count = len(state.get("pending_enables", []))
    pending_count += len(state.get("context_diffs", {}))

    return pending_count


def take_session_snapshot(state: Any, config: _Config) -> SessionSnapshot:
    """Capture current state for reset capability."""
    context_dir = config.village_dir / "context"

    initial_files: dict[str, str] = {}
    current_files: dict[str, str] = {}

    for filename in [
        "project.md",
        "goals.md",
        "constraints.md",
        "assumptions.md",
        "decisions.md",
        "open-questions.md",
    ]:
        file_path = context_dir / filename
        if file_path.exists():
            current_files[filename] = file_path.read_text(encoding="utf-8")

    snapshot = SessionSnapshot(
        start_time=datetime.now(),
        batch_id=f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        initial_context_files=initial_files,
        current_context_files=current_files,
        pending_enables=state.pending_enables.copy(),
        created_task_ids=[],
    )

    state.session_snapshot = snapshot
    logger.debug(f"Captured session snapshot: {snapshot.batch_id}")

    return snapshot
