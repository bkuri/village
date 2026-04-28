"""Environment sanitizer — clean execution environment for agent commands.

Every agent command runs in a sanitized, minimal environment to prevent:

- **PATH injection**: agent adds ``/tmp/evil`` to PATH
- **Python module shadowing**: agent writes a malicious ``conftest.py``
- **SSH key reuse**: agent steals the host's SSH agent socket
- **LD_PRELOAD attacks**: agent loads arbitrary shared libraries
- **Git directory confusion**: agent manipulates ``GIT_DIR``,
  ``GIT_WORK_TREE``, or ``GIT_INDEX_FILE``
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

logger = __import__("logging").getLogger(__name__)


@dataclass
class SanitizedEnv:
    """A clean environment for executing agent commands.

    Attributes:
        env: The sanitized environment dictionary.
        worktree: The worktree path used as HOME/PWD.
    """

    env: dict[str, str]
    worktree: Path


class EnvironmentSanitizer:
    """Sanitizes the execution environment for agent commands.

    Builds a minimal, predictable environment from scratch — never inheriting
    the parent process's environment directly. Known-dangerous variables are
    stripped unconditionally.

    Args:
        worktree: The worktree directory. Used as ``HOME`` and ``PWD`` for
            the sanitized environment.
        home: Override for ``HOME``. If omitted, *worktree* is used.
    """

    # Known-safe PATHs
    SAFE_PATHS: list[str] = [
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/local/sbin",
        "/usr/sbin",
    ]

    # Environment variables that are always unset
    STRIPPED_VARS: set[str] = {
        "SSH_AUTH_SOCK",  # No SSH agent forwarding
        "SSH_AGENT_PID",  # No SSH agent
        "PYTHONPATH",  # No Python path shadowing
        "PYTHONSTARTUP",  # No Python startup scripts
        "LD_PRELOAD",  # No dynamic library injection
        "LD_LIBRARY_PATH",  # No library path injection
        "BASH_ENV",  # No bash startup scripts
        "ENV",  # No sh startup scripts
        "GIT_DIR",  # Don't let agent control git dir
        "GIT_WORK_TREE",  # Don't let agent control git worktree
        "GIT_INDEX_FILE",  # Don't let agent control git index
    }

    def __init__(self, worktree: Path, home: Path | None = None) -> None:
        self.worktree = worktree.resolve()
        self.home = (home or worktree).resolve()

    def sanitize(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Build a clean environment for command execution.

        Starts from a minimal base consisting of:

        - ``PATH`` = :attr:`SAFE_PATHS`
        - ``HOME`` = the configured home directory
        - ``PWD`` = the worktree

        Then applies *extra* variables (execution engine overrides).
        Finally, all :attr:`STRIPPED_VARS` are removed regardless.

        Args:
            extra: Optional dictionary of additional environment variables
                to include (overrides the minimal base).

        Returns:
            A new environment dictionary.
        """
        # Build minimal base
        env: dict[str, str] = {
            "PATH": ":".join(self.SAFE_PATHS),
            "HOME": str(self.home),
            "PWD": str(self.worktree),
        }

        # Preserve locale-related variables for correct tool behavior
        for key in ("LANG", "LC_ALL", "LC_MESSAGES", "LC_CTYPE"):
            value = os.environ.get(key)
            if value is not None:
                env[key] = value

        # Preserve TERM for tools that need it (e.g. git diff coloring)
        term = os.environ.get("TERM")
        if term is not None:
            env["TERM"] = term

        # Preserve USER for tools that check identity
        user = os.environ.get("USER")
        if user is not None:
            env["USER"] = user

        # Apply overrides
        if extra:
            # Extra vars go last so they override the base
            for key, value in extra.items():
                if key not in self.STRIPPED_VARS:
                    env[key] = value

        # Strip dangerous variables
        for key in self.STRIPPED_VARS:
            env.pop(key, None)

        return env

    def to_env_dict(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Convenience method that calls :meth:`sanitize` and returns the dict.

        Args:
            extra: Optional dictionary of additional environment variables.

        Returns:
            A sanitized environment dictionary.
        """
        return self.sanitize(extra=extra)
