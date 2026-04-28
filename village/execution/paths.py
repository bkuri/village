"""Path resolution and access control — symlink escape detection and path policies.

Every path operation in the execution engine must go through this module to
prevent symlink-based escape attacks.  A malicious symlink inside the worktree
can point outside it (e.g. ``ln -s ../../.village/rules.yaml rules.yaml``),
bypassing normal path restrictions.

Defence in depth: three layers

1. :func:`resolve_safe_path` — resolve a path following all symlinks, raising
   if the real location escapes the worktree.
2. :func:`is_within_worktree` — boolean predicate for quick checks.
3. :class:`PathPolicy` — full read/write policy with protected directories.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_safe_path(target: Path, worktree: Path) -> Path:
    """Resolve a path to its real location, checking it stays within the worktree.

    Uses :meth:`Path.resolve` to follow all symlinks.
    Raises :exc:`ValueError` if the resolved path escapes the worktree.

    Args:
        target: The (possibly symlinked) path to resolve.
        worktree: The worktree root that *target* must stay within.

    Returns:
        The fully resolved :class:`Path`.

    Raises:
        ValueError: If the resolved path falls outside the worktree.
    """
    real_target = target.resolve()
    real_worktree = worktree.resolve()

    if not str(real_target).startswith(str(real_worktree)):
        raise ValueError(
            f"Path {target} resolves to {real_target}, "
            f"which is outside the worktree {real_worktree}"
        )

    return real_target


def is_within_worktree(path: Path, worktree: Path) -> bool:
    """Check if a (possibly symlinked) path is within the worktree.

    Uses :meth:`Path.resolve` to catch symlink escape attempts.
    Always returns False for paths that contain ``..`` and resolve outside.

    Args:
        path: The path to check.
        worktree: The worktree root.

    Returns:
        True if the path is safely inside the worktree.
    """
    try:
        resolve_safe_path(path, worktree)
        return True
    except ValueError:
        return False


def sanitize_paths(files: list[Path], worktree: Path) -> tuple[list[Path], list[Path]]:
    """Split file list into safe and unsafe paths.

    Symlink escapes are moved to *unsafe_paths*.

    Args:
        files: List of paths to check.
        worktree: The worktree root.

    Returns:
        ``(safe_paths, unsafe_paths)``.
    """
    safe: list[Path] = []
    unsafe: list[Path] = []
    for f in files:
        if is_within_worktree(f, worktree):
            safe.append(f)
        else:
            logger.warning("Path %s escapes worktree — rejecting", f)
            unsafe.append(f)
    return safe, unsafe


class PathPolicy:
    """Path-based access control.

    Enforces:

    - All operations must stay within the worktree.
    - Protected directories (``specs/``, ``.village/``, ``.git/``) are
      read-only (cannot be written to).
    - Symlinks cannot escape the worktree.

    Args:
        worktree: The worktree root directory.
    """

    PROTECTED_PATTERNS: list[str] = [
        "specs/*",
        ".village/**",
        ".git/**",
        "**/*.lock",
        "**/.env*",
        "**/credentials*",
        "**/secrets*",
    ]

    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree.resolve()

    def can_write(self, path: Path) -> tuple[bool, str | None]:
        """Check if a path is allowed for writing.

        Args:
            path: The path to check.

        Returns:
            ``(allowed, reason)`` — *reason* is ``None`` if allowed.
        """
        try:
            real = resolve_safe_path(path, self.worktree)
        except ValueError:
            return False, f"Path escapes worktree: {path}"

        rel = str(real.relative_to(self.worktree))
        for pattern in self.PROTECTED_PATTERNS:
            if fnmatch.fnmatch(rel, pattern):
                return False, f"Protected path: {rel} matches {pattern}"

        return True, None

    def can_read(self, path: Path) -> bool:
        """Check if a path is allowed for reading.

        Reading is allowed as long as it is within the worktree.

        Args:
            path: The path to check.

        Returns:
            True if the path is safe to read.
        """
        return is_within_worktree(path, self.worktree)
