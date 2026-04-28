"""Build reference freezing — tamper-proof config reads from git.

Freezes the current HEAD commit at build start. All config reads during the
build use this commit hash, making config files tamper-proof from the agent's
perspective. The agent can write anything to disk — the builder reads from
git objects.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def freeze_build_commit(repo_root: Path) -> str:
    """Capture the current HEAD commit hash at build start.

    All config reads during the build use this commit hash,
    making config files tamper-proof from the agent's perspective.
    The agent can write anything to disk — the builder reads from git objects.

    Args:
        repo_root: The git repository root directory.

    Returns:
        The full SHA-1 commit hash of HEAD.

    Raises:
        RuntimeError: If git rev-parse fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        commit = result.stdout.strip()
        logger.info("Build frozen at commit: %s", commit)
        return commit
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to freeze build commit: {e}") from e


def git_show(repo_root: Path, commit: str, path: str) -> str | None:
    """Read a file from a specific git commit (not from working tree).

    This is the core tamper-proof mechanism. Even if the agent modifies
    .village/rules.yaml on disk, this reads the original from git objects.

    Args:
        repo_root: The git repository root directory.
        commit: The commit SHA or ref to read from.
        path: The file path within the repo (e.g. ``.village/rules.yaml``).

    Returns:
        The file content as a string, or None if the path does not exist
        at the given commit.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        logger.debug("Path '%s' not found at commit %s", path, commit)
        return None
