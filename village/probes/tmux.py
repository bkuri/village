"""Tmux runtime probes."""

import logging
import pathlib
import shutil
import subprocess
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
        "-s",
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


def _is_terminal_wide_enough(required_length: int) -> bool:
    """
    Check if terminal is wide enough for indicator.

    Uses shutil.get_terminal_size() to get current terminal dimensions.
    Returns True if there's enough space for indicator + base name.

    Heuristic: Assume at least 30 columns are needed for comfortable display.
    """
    try:
        columns, _ = shutil.get_terminal_size()
        return columns >= required_length
    except Exception:
        return False


def rename_window(session_name: str, old_name: str, new_name: str) -> bool:
    """
    Rename a tmux window.

    Args:
        session_name: Tmux session name
        old_name: Current window name (to find it)
        new_name: New window name

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ["tmux", "list-windows", "-t", session_name, "-F", "'#{window_index} #{window_name}'"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False

        window_index = None
        for line in result.stdout.split("\n"):
            if old_name in line:
                window_index = line.split()[0].strip("'")
                break
        else:
            return False

        rename_cmd = ["tmux", "rename-window", "-t", f"{session_name}:{window_index}", new_name]
        result = subprocess.run(rename_cmd, capture_output=True, text=True, check=False)

        return result.returncode == 0

    except Exception:
        return False


def get_current_window(session_name: str) -> str | None:
    """
    Get the current window name for a session.

    Args:
        session_name: Tmux session name

    Returns:
        Window name or None if not in session
    """
    try:
        cmd = ["tmux", "display-message", "-p", "-t", session_name, "'#{window_name}'"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        return result.stdout.strip().strip("'") if result.returncode == 0 else None

    except Exception:
        return None


def set_window_indicator(
    session_name: str,
    base_name: str | None = None,
    draft_id: str | None = None,
    task_id: str | None = None,
) -> bool:
    """
    Set window indicator based on active editing.

    Args:
        session_name: Tmux session name
        base_name: Original window name (or None to detect current)
        draft_id: Active draft ID (or None)
        task_id: Active task ID (or None, for future)

    Returns:
        True if successful, False otherwise

    Indicator priority:
      1. [DRAFT <draft-id>] - Active draft editing
      2. [TASK <task-id>] - Active task editing (future)
      3. [TC] - Task-Create mode (no active draft)
      4. <original> - Default (no active editing)
    """
    try:
        if base_name is None:
            base_name = get_current_window(session_name)
            if base_name is None:
                return False

        indicator = ""
        if draft_id:
            indicator = f"[DRAFT {draft_id}]"
            if not _is_terminal_wide_enough(len(indicator) + len(base_name) + 5):
                return True
        elif task_id:
            indicator = f"[TASK {task_id}]"
            if not _is_terminal_wide_enough(len(indicator) + len(base_name) + 5):
                return True
        else:
            if base_name.startswith("[DRAFT ") or base_name.startswith("[TASK "):
                base_name = " ".join(base_name.split()[1:])

        if indicator:
            new_name = f"{indicator} {base_name}" if base_name else indicator
        else:
            new_name = base_name

        return rename_window(session_name, base_name, new_name)

    except Exception:
        return False


def load_village_config(village_dir: pathlib.Path) -> bool:
    """
    Load Village tmux configuration file.

    Loads .village/tmux.conf and applies it to current session.
    Configuration contains status bar formatting, colors, and variables.

    Args:
        village_dir: Path to .village directory

    Returns:
        True if successful, False otherwise
    """
    config_path = village_dir / "tmux.conf"

    if not config_path.exists():
        logger.debug(f"Village tmux config not found: {config_path}")
        return False

    try:
        cmd = ["tmux", "source-file", str(config_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            logger.error(f"Failed to load tmux config: {result.stderr}")
            return False

        logger.debug(f"Loaded tmux config from {config_path}")
        return True

    except OSError as e:
        logger.error(f"Error loading tmux config: {e}")
        return False


def update_status_mode(mode: str) -> bool:
    """
    Update tmux status bar mode indicator.

    Sets @village_mode variable which is referenced in .village/tmux.conf.

    Args:
        mode: Mode indicator (e.g., "#NORMAL", "#CREATE", "#DRAFT df-xxxx", "#TASK bd-xxxx")

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ["tmux", "set-environment", "-g", "@village_mode", mode]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            logger.debug(f"Failed to update status mode: {result.stderr}")
            return False

        logger.debug(f"Updated status mode: {mode}")
        return True

    except OSError:
        return False


def update_status_draft_count(count: int) -> bool:
    """
    Update tmux status bar draft count.

    Sets @village_draft_count variable which is referenced in .village/tmux.conf.

    Args:
        count: Number of drafts

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ["tmux", "set-environment", "-g", "@village_draft_count", str(count)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            logger.debug(f"Failed to update draft count: {result.stderr}")
            return False

        logger.debug(f"Updated draft count: {count}")
        return True

    except OSError:
        return False


def update_status_border_colour(colour: str) -> bool:
    """
    Update tmux pane border colour.

    Sets @village_border_colour variable and updates active border style.

    Args:
        colour: Colour name (e.g., "blue", "green", "red")

    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ["tmux", "set-environment", "-g", "@village_border_colour", colour]
        subprocess.run(cmd, capture_output=True, text=True, check=False)

        if colour == "green":
            style = "fg=green"
        elif colour == "red":
            style = "fg=red"
        elif colour == "blue":
            style = "fg=blue"
        else:
            style = "fg=colour238"

        cmd = ["tmux", "set-option", "-g", "pane-active-border-style", style]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        logger.debug(f"Updated border colour: {colour} ({style})")
        return result.returncode == 0

    except OSError:
        return False
