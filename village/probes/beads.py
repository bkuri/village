"""Beads availability detection."""

import logging
from dataclasses import dataclass
from typing import Optional

from village.probes.repo import find_git_root
from village.probes.tools import SubprocessError, run_command_output

logger = logging.getLogger(__name__)


@dataclass
class BeadsStatus:
    """Beads availability and initialization status."""

    command_available: bool
    command_path: Optional[str] = None
    version: Optional[str] = None
    repo_initialized: bool = False
    beads_dir_exists: bool = False
    error: Optional[str] = None


def beads_available() -> BeadsStatus:
    """
    Check if Beads (bd command) is available and repo initialized.

    Returns:
        BeadsStatus with detailed availability information
    """
    cmd_path: Optional[str] = None
    try:
        cmd_path = run_command_output(["which", "bd"])
    except SubprocessError:
        return BeadsStatus(
            command_available=False,
            error="bd command not found in PATH",
        )

    version: Optional[str] = None
    try:
        version = run_command_output(["bd", "--version"])
        logger.debug(f"Beads command functional: {cmd_path} ({version})")
    except SubprocessError as e:
        return BeadsStatus(
            command_available=False,
            command_path=cmd_path,
            error=f"bd command found but not functional: {e}",
        )

    repo_initialized = False
    beads_dir_exists = False
    try:
        git_root = find_git_root()
        beads_dir = git_root / ".beads"
        beads_dir_exists = beads_dir.exists()
        repo_initialized = beads_dir.exists() and beads_dir.is_dir()
        logger.debug(f"Beads repo initialized: {repo_initialized} ({beads_dir})")
    except RuntimeError:
        logger.debug("Not in git repo, skipping beads init check")
        repo_initialized = False

    return BeadsStatus(
        command_available=True,
        command_path=cmd_path,
        version=version,
        repo_initialized=repo_initialized,
        beads_dir_exists=beads_dir_exists,
    )


def beads_ready_capability() -> bool:
    """
    Check if Beads is ready to provide task readiness.

    Returns:
        True if beads available and initialized
    """
    status = beads_available()
    return status.command_available and status.repo_initialized
