"""Runtime lifecycle management."""

import logging
from dataclasses import dataclass

from village.config import get_config
from village.probes.tmux import (
    create_session,
    create_window,
    kill_session,
    list_windows,
    session_exists,
)
from village.probes.tools import SubprocessError, run_command

logger = logging.getLogger(__name__)


@dataclass
class InitializationPlan:
    """Plan for village up operation."""

    needs_session: bool
    needs_directories: bool
    needs_beads_init: bool
    session_exists: bool
    directories_exist: bool
    beads_initialized: bool


@dataclass
class RuntimeState:
    """Current runtime state."""

    session_exists: bool
    directories_exist: bool
    beads_initialized: bool
    session_name: str


def collect_runtime_state(session_name: str) -> RuntimeState:
    """Gather current runtime state via probes."""
    config = get_config()
    beads_dir = config.git_root / ".beads"

    return RuntimeState(
        session_exists=session_exists(session_name),
        directories_exist=config.village_dir.exists(),
        beads_initialized=beads_dir.exists(),
        session_name=session_name,
    )


def plan_initialization(state: RuntimeState) -> InitializationPlan:
    """Plan what needs to be created/initialized."""
    return InitializationPlan(
        needs_session=not state.session_exists,
        needs_directories=not state.directories_exist,
        needs_beads_init=not state.beads_initialized,
        session_exists=state.session_exists,
        directories_exist=state.directories_exist,
        beads_initialized=state.beads_initialized,
    )


def _ensure_directories(dry_run: bool) -> bool:
    """Ensure village directories exist."""
    config = get_config()

    if config.village_dir.exists():
        logger.debug("Directories already exist")
        return True

    if not dry_run:
        config.ensure_exists()
        logger.debug(f"Created directories at {config.village_dir}")
        return True

    return False


def _ensure_beads_initialized(dry_run: bool) -> bool:
    """Ensure Beads is initialized (if available)."""
    config = get_config()

    if (config.git_root / ".beads").exists():
        logger.debug("Beads already initialized")
        return True

    if not dry_run:
        try:
            run_command(["bd", "init"], check=True)
            logger.debug(f"Initialized Beads in {config.git_root}")
            return True
        except SubprocessError:
            logger.debug("Beads command not available, skipping initialization")
            return True

    return False


def _ensure_session(dry_run: bool) -> bool:
    """Ensure tmux session exists."""
    config = get_config()

    if session_exists(config.tmux_session):
        logger.debug(f"Session '{config.tmux_session}' already exists")
        return True

    if not dry_run:
        success = create_session(config.tmux_session)
        return success

    return False


def _create_dashboard(session_name: str, dry_run: bool) -> bool:
    """
    Create dashboard window with status overview.

    Uses `watch -n 2 village status --short` for portability.
    """
    dashboard_name = "village:dashboard"
    dashboard_command = "watch -n 2 village status --short"

    if not dry_run:
        # Cheap check: does dashboard window exist?
        windows = list_windows(session_name)
        dashboard_exists = dashboard_name in windows

        if dashboard_exists:
            logger.debug("Dashboard window already exists")
            return True

        # Create dashboard window
        success = create_window(session_name, dashboard_name, dashboard_command)
        return success

    return False


def execute_initialization(
    plan: InitializationPlan,
    *,
    dry_run: bool = False,
    dashboard: bool = True,
) -> bool:
    """
    Execute initialization plan (or preview if dry_run).

    Idempotent: Only creates missing components.

    Returns True if successful, False on error.
    """
    config = get_config()

    # Step 1: Create directories (idempotent)
    if plan.needs_directories:
        if not _ensure_directories(dry_run):
            return False

    # Step 2: Create session (idempotent)
    if plan.needs_session:
        if not _ensure_session(dry_run):
            return False

    # Step 3: Initialize Beads (if needed)
    if plan.needs_beads_init:
        if not _ensure_beads_initialized(dry_run):
            return False

    # Step 4: Create dashboard (idempotent, with cheap check)
    if dashboard:
        if not _create_dashboard(config.tmux_session, dry_run):
            return False

    return True


def shutdown_runtime(session_name: str) -> bool:
    """
    Stop village runtime (kill tmux session).

    Does not delete work data (locks, worktrees, .village/).

    Returns True if successful, False on error.
    """
    if not session_exists(session_name):
        logger.debug(f"Session '{session_name}' does not exist")
        return True

    return kill_session(session_name)
