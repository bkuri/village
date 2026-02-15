"""Lock file handling."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.probes.tmux import pane_exists, panes

logger = logging.getLogger(__name__)


@dataclass
class Lock:
    """Lock file data."""

    task_id: str
    pane_id: str
    window: str
    agent: str
    claimed_at: datetime
    _config: Optional[Config] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self._config is None:
            self._config = get_config()

    @property
    def path(self) -> Path:
        """Compute lock file path."""
        if self._config is None:
            raise RuntimeError("Lock not initialized properly")
        return self._config.locks_dir / f"{self.task_id}.lock"


def parse_lock(lock_path: Path) -> Optional[Lock]:
    """
    Parse lock file from disk with validation.

    Args:
        lock_path: Path to lock file

    Returns:
        Lock object if valid, None if corrupt/invalid
    """
    if not lock_path.exists():
        return None

    try:
        content = lock_path.read_text(encoding="utf-8")
        data = {}

        for line in content.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()

        # Validate required fields
        required_fields = {
            "id": "task_id",
            "pane": "pane_id",
            "window": "window",
            "agent": "agent",
            "claimed_at": "claimed_at",
        }

        for lock_key, _ in required_fields.items():
            if lock_key not in data:
                logger.error(f"Corrupted lock {lock_path}: missing field '{lock_key}'")
                return None

            if not data[lock_key].strip():
                logger.error(f"Corrupted lock {lock_path}: empty field '{lock_key}'")
                return None

        # Validate datetime format
        claimed_at_str = data["claimed_at"]
        try:
            claimed_at = datetime.fromisoformat(claimed_at_str)
        except ValueError as e:
            logger.error(f"Corrupted lock {lock_path}: invalid datetime: {e}")
            return None

        return Lock(
            task_id=data["id"],
            pane_id=data["pane"],
            window=data["window"],
            agent=data["agent"],
            claimed_at=claimed_at,
        )
    except (IOError, OSError) as e:
        logger.error(f"Failed to read lock file {lock_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing lock {lock_path}: {e}")
        return None


def write_lock(lock: Lock) -> None:
    """
    Write lock file to disk (atomic).

    Args:
        lock: Lock object to write
    """
    content = (
        f"id={lock.task_id}\n"
        f"pane={lock.pane_id}\n"
        f"window={lock.window}\n"
        f"agent={lock.agent}\n"
        f"claimed_at={lock.claimed_at.isoformat()}\n"
    )

    # Ensure parent directory exists
    lock.path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write
    temp_path = lock.path.with_suffix(".tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(lock.path)
        logger.debug(f"Wrote lock: {lock.path}")
    except (IOError, OSError) as e:
        logger.error(f"Failed to write lock {lock.path}: {e}")
        raise


def is_active(lock: Lock, session_name: str, force_refresh: bool = False) -> bool:
    """
    Evaluate if lock is ACTIVE or STALE.

    ACTIVE: pane exists
    STALE: pane doesn't exist

    Args:
        lock: Lock object to evaluate
        session_name: Tmux session name
        force_refresh: Force fresh pane check

    Returns:
        True if ACTIVE, False if STALE
    """
    return pane_exists(session_name, lock.pane_id, force_refresh=force_refresh)


def evaluate_locks(locks: list[Lock], session_name: str, *, force_refresh: bool = False) -> dict[str, bool]:
    """
    Batch evaluate ACTIVE/STALE for all locks.

    Args:
        locks: List of Lock objects
        session_name: Tmux session name
        force_refresh: Force fresh pane check

    Returns:
        Dictionary mapping task_id -> is_active (True=ACTIVE, False=STALE)
    """
    all_panes = panes(session_name, force_refresh=force_refresh)
    return {lock.task_id: lock.pane_id in all_panes for lock in locks}
