"""Configuration loader."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from village.probes.repo import find_git_root

TMUX_SESSION = "village"
DEFAULT_WORKTREES_DIR_NAME = ".worktrees"

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Village configuration."""

    git_root: Path
    village_dir: Path
    worktrees_dir: Path
    tmux_session: str = TMUX_SESSION
    _config_path: Path = field(init=False)
    locks_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        """Compute derived paths."""
        self._config_path = self.village_dir / "config"
        self.locks_dir = self.village_dir / "locks"

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self._config_path

    def config_exists(self) -> bool:
        """Check if config file exists."""
        return self._config_path.exists()

    def ensure_exists(self) -> None:
        """Ensure village directories exist (mutating)."""
        logger.debug(f"Creating {self.village_dir}")
        self.village_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Creating {self.locks_dir}")
        self.locks_dir.mkdir(exist_ok=True)
        logger.debug(f"Creating {self.worktrees_dir}")
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    """
    Get current configuration.

    Resolves from:
    1. Git repo root (required)
    2. Environment variables (optional)

    Returns:
        Config object with resolved paths

    Raises:
        RuntimeError: If not in a git repository
    """
    git_root = find_git_root()

    # Override paths from env vars if provided
    village_dir = Path(os.environ.get("VILLAGE_DIR", git_root / ".village"))
    worktrees_dir = Path(
        os.environ.get(
            "VILLAGE_WORKTREES_DIR",
            git_root / DEFAULT_WORKTREES_DIR_NAME,
        )
    )

    logger.debug(f"Git root: {git_root}")
    logger.debug(f"Village dir: {village_dir}")
    logger.debug(f"Worktrees dir: {worktrees_dir}")

    return Config(
        git_root=git_root,
        village_dir=village_dir,
        worktrees_dir=worktrees_dir,
    )
