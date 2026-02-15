"""Session state management for Village Chat."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object

logger = logging.getLogger(__name__)


class SessionStateEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and dataclass objects."""

    def default(self, o: object) -> object:
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


@dataclass
class SessionSnapshot:
    """Capture state for reset capability."""

    start_time: datetime
    batch_id: str
    initial_context_files: dict[str, str]
    current_context_files: dict[str, str]
    pending_enables: list[str]
    created_task_ids: list[str]

    # Brainstorm-specific fields
    brainstorm_baseline: Optional[dict[str, Any]] = None
    brainstorm_created_ids: list[str] = field(default_factory=list)
    brainstorm_batch_id: Optional[str] = None


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

    if hasattr(state, "created_task_ids"):
        session_data["created_task_ids"] = state.created_task_ids
    if hasattr(state, "session_snapshot") and state.session_snapshot:
        if isinstance(state.session_snapshot, SessionSnapshot):
            session_data["session_snapshot"] = state.session_snapshot.__dict__
        else:
            session_data["session_snapshot"] = state.session_snapshot

    session_file.write_text(
        json.dumps(session_data, indent=2, cls=SessionStateEncoder),
        encoding="utf-8",
    )
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
