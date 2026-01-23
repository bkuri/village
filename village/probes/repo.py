"""Git repository probes."""

import logging
from pathlib import Path

from village.probes.tools import SubprocessError, run_command_output

logger = logging.getLogger(__name__)


def find_git_root() -> Path:
    """
    Find git repository root.

    Returns:
        Path to git repository root

    Raises:
        RuntimeError: If not in a git repository
    """
    try:
        root_str = run_command_output(["git", "rev-parse", "--show-toplevel"])
        root = Path(root_str)
        logger.debug(f"Git root: {root}")
        return root
    except (SubprocessError, FileNotFoundError) as e:
        logger.debug(f"Not in git repo: {e}")
        raise RuntimeError("Not in a git repository") from e
