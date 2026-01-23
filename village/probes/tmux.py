"""Tmux runtime probes."""

import logging
import time
from dataclasses import dataclass

from village.probes.tools import SubprocessError, run_command, run_command_output

logger = logging.getLogger(__name__)

_CACHE_TTL = 5.0


@dataclass
class _PaneSnapshot:
    panes: set[str]
    ts: float


_panes_cache: dict[str, _PaneSnapshot] = {}


def clear_pane_cache() -> None:
    _panes_cache.clear()
    logger.debug("Pane cache cleared")


def session_exists(session_name: str) -> bool:
    """Check if tmux session exists."""
    cmd = ["tmux", "has-session", "-t", session_name]
    result = run_command(cmd, capture=False, check=False)
    exists = result.returncode == 0
    logger.debug(f"Session '{session_name}' exists: {exists}")
    return exists


def list_sessions() -> list[str]:
    """List all tmux sessions."""
    try:
        output = run_command_output(["tmux", "list-sessions", "-F", "#{session_name}"])
        sessions = [line for line in output.split("\n") if line]
        logger.debug(f"Sessions: {sessions}")
        return sessions
    except SubprocessError:
        logger.debug("No tmux sessions")
        return []


def _list_panes(session_name: str) -> set[str]:
    """List all panes for a session (fresh, no cache)."""
    cmd = [
        "tmux",
        "list-panes",
        "-t",
        session_name,
        "-F",
        "#{pane_id}",
    ]
    output = run_command_output(cmd)
    return {line.strip() for line in output.splitlines() if line.strip()}


def panes(session_name: str, *, force_refresh: bool = False) -> set[str]:
    """
    Get pane IDs for a session (cached).

    Args:
        session_name: Name of tmux session
        force_refresh: Force fresh snapshot

    Returns:
        Set of pane IDs (empty if session doesn't exist)
    """
    now = time.time()
    snap = _panes_cache.get(session_name)

    if not force_refresh and snap and (now - snap.ts) < _CACHE_TTL:
        logger.debug("Pane snapshot cache hit: %s (%d panes)", session_name, len(snap.panes))
        return snap.panes

    try:
        pane_set = _list_panes(session_name)
    except SubprocessError:
        pane_set = set()

    _panes_cache[session_name] = _PaneSnapshot(panes=pane_set, ts=now)
    logger.debug("Pane snapshot refreshed: %s (%d panes)", session_name, len(pane_set))
    return pane_set


def refresh_panes(session_name: str) -> set[str]:
    """
    Force refresh of pane snapshot for a session.

    Alias for panes(session_name, force_refresh=True).
    Call this after tmux mutations (creating/deleting panes).

    Args:
        session_name: Name of tmux session

    Returns:
        Fresh set of pane IDs
    """
    return panes(session_name, force_refresh=True)


def pane_exists(session_name: str, pane_id: str, *, force_refresh: bool = False) -> bool:
    """
    Check if pane exists in session (cached).

    Args:
        session_name: Name of tmux session
        pane_id: Pane ID (e.g., "%12")
        force_refresh: Force fresh snapshot

    Returns:
        True if pane exists, False otherwise
    """
    return pane_id in panes(session_name, force_refresh=force_refresh)


def create_session(session_name: str) -> bool:
    """
    Create tmux session if it doesn't exist.

    Returns True if created or already exists, False on error.
    """
    if session_exists(session_name):
        logger.debug(f"Session '{session_name}' already exists")
        return True

    cmd = ["tmux", "new-session", "-d", "-s", session_name]
    try:
        run_command(cmd, check=True)
        logger.debug(f"Created tmux session '{session_name}'")
        return True
    except SubprocessError as e:
        logger.error(f"Failed to create tmux session: {e}")
        return False


def kill_session(session_name: str) -> bool:
    """
    Kill tmux session if it exists.

    Returns True if killed or didn't exist, False on error.
    """
    if not session_exists(session_name):
        logger.debug(f"Session '{session_name}' does not exist")
        return True

    cmd = ["tmux", "kill-session", "-t", session_name]
    try:
        run_command(cmd, check=True)
        logger.debug(f"Killed tmux session '{session_name}'")
        return True
    except SubprocessError as e:
        logger.error(f"Failed to kill tmux session: {e}")
        return False


def create_window(session_name: str, window_name: str, command: str) -> bool:
    """
    Create a new window in existing session.

    Used for dashboard and resume operations.

    Returns True if created, False on error.
    """
    cmd = ["tmux", "new-window", "-t", session_name, "-n", window_name, command]
    try:
        run_command(cmd, check=True)
        logger.debug(f"Created tmux window '{window_name}' in session '{session_name}'")
        return True
    except SubprocessError as e:
        logger.error(f"Failed to create tmux window: {e}")
        return False


def list_windows(session_name: str) -> list[str]:
    """
    List all windows in a session.

    Returns list of window names, or empty list if session doesn't exist.
    """
    if not session_exists(session_name):
        return []

    cmd = ["tmux", "list-windows", "-t", session_name, "-F", "#{window_name}"]
    try:
        output = run_command_output(cmd)
        windows = [line for line in output.splitlines() if line.strip()]
        logger.debug(f"Windows in session '{session_name}': {windows}")
        return windows
    except SubprocessError as e:
        logger.debug(f"Failed to list windows: {e}")
        return []


def send_keys(session_name: str, target: str, keys: str) -> bool:
    """
    Send keys to tmux pane (for dashboard refresh).

    Args:
        session_name: Tmux session
        target: Target pane (e.g., "village:dashboard")
        keys: Keys to send (e.g., "C-m" for Enter)

    Returns True on success, False on error.
    """
    cmd = ["tmux", "send-keys", "-t", target, keys]
    try:
        run_command(cmd, check=True)
        logger.debug(f"Sent keys '{keys}' to pane '{target}'")
        return True
    except SubprocessError as e:
        logger.debug(f"Failed to send keys: {e}")
        return False
