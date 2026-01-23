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
