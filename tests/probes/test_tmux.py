"""Test tmux pane caching."""

import os
import subprocess
from unittest.mock import patch

import pytest

from village.probes.tmux import (
    _panes_cache,
    clear_pane_cache,
    pane_exists,
    panes,
    refresh_panes,
    session_exists,
)
from village.probes.tools import SubprocessError


@pytest.fixture(autouse=True)
def reset_pane_cache():
    """Clear pane cache before each test."""
    clear_pane_cache()
    yield
    clear_pane_cache()


def test_panes_returns_set():
    """Test that panes() returns a set."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n%13\n"

        result = panes("test-session")

        assert isinstance(result, set)
        assert "%12" in result
        assert "%13" in result


def test_panes_caches_result():
    """Test that panes() caches results."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n"

        panes("test-session")
        assert mock_run.call_count == 1

        panes("test-session")
        assert mock_run.call_count == 1  # Cache hit


def test_panes_force_refresh():
    """Test that force_refresh bypasses cache."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n"

        panes("test-session")
        assert mock_run.call_count == 1

        panes("test-session", force_refresh=True)
        assert mock_run.call_count == 2


def test_refresh_panes_alias():
    """Test that refresh_panes() is an alias for force_refresh."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n"

        panes("test-session")
        assert mock_run.call_count == 1

        refresh_panes("test-session")
        assert mock_run.call_count == 2


def test_panes_handles_subprocess_error():
    """Test that panes() handles SubprocessError gracefully."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.side_effect = SubprocessError("session not found")

        result = panes("test-session")

        assert result == set()
        assert "test-session" in _panes_cache


def test_panes_per_session_caching():
    """Test that caching is per-session."""
    with patch("village.probes.tmux.run_command_output") as mock_run:

        def side_effect(cmd):
            if "session1" in cmd:
                return "%12\n"
            elif "session2" in cmd:
                return "%13\n"
            raise SubprocessError("unknown session")

        mock_run.side_effect = side_effect

        panes1 = panes("session1")
        panes2 = panes("session2")

        assert panes1 == {"%12"}
        assert panes2 == {"%13"}
        assert mock_run.call_count == 2


def test_pane_exists():
    """Test pane existence check."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n%13\n"

        assert pane_exists("test-session", "%12") is True
        assert pane_exists("test-session", "%13") is True
        assert pane_exists("test-session", "%99") is False


def test_clear_pane_cache():
    """Test cache clearing."""
    with patch("village.probes.tmux.run_command_output") as mock_run:
        mock_run.return_value = "%12\n"

        panes("test-session")
        assert len(_panes_cache) == 1

        clear_pane_cache()
        assert len(_panes_cache) == 0


@pytest.mark.integration
def test_tmux_probes_against_real_session():
    """
    Test tmux probes with real ephemeral session.

    Scenario A: Tests pane snapshot truth model end-to-end.
    """
    pytest.importorskip("tmux", reason="tmux not available")

    session_name = f"village-test-{os.getpid()}"
    pane_id = None

    try:
        # Create session with window
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            check=True,
        )

        # Assert session exists
        assert session_exists(session_name) is True

        # Get panes
        panes_set = panes(session_name)
        assert len(panes_set) > 0, "Session should have at least one pane"

        pane_id = list(panes_set)[0]

        # Assert pane exists
        assert pane_exists(session_name, pane_id) is True

        # Test cache - second call should use cache
        panes_set2 = panes(session_name)
        assert panes_set2 == panes_set

        # Test force refresh
        panes_set3 = panes(session_name, force_refresh=True)
        assert panes_set3 == panes_set

    finally:
        # Cleanup: kill session
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            check=False,
        )

        # Assert session gone
        assert session_exists(session_name) is False

        # Assert panes empty after force refresh
        panes_empty = panes(session_name, force_refresh=True)
        assert len(panes_empty) == 0

        # Assert previously-known pane is now gone
        if pane_id:
            assert pane_exists(session_name, pane_id) is False


# TODO (Phase 7/8): Add Scenario B - lock classification integration test
# This test will validate ACTIVE/STALE lock correctness against real tmux panes.
# Requires lock parsing from Phase 3 and stable lock system.


@pytest.mark.integration
def test_lock_classification_integration():
    """
    Test ACTIVE/STALE lock classification against real tmux.

    Scenario B: Validates lock correctness with real panes.
    Uses ephemeral tmux session always.
    """
    pytest.importorskip("tmux", reason="tmux not available")

    from datetime import datetime, timezone

    from village.locks import Lock, is_active, write_lock

    # Use ephemeral session (always)
    session_name = f"village-test-{os.getpid()}"
    pane_id = None
    fake_pane_id = "%99999"

    try:
        # Create ephemeral session with window
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            check=True,
        )

        # Create test window
        subprocess.run(
            ["tmux", "new-window", "-d", "-t", session_name, "-n", "village-test-window"],
            check=True,
        )

        # Get panes (force refresh)
        panes_set = panes(session_name, force_refresh=True)
        assert len(panes_set) > 0, "Session should have at least one pane"

        pane_id = list(panes_set)[0]

        # Write lock with real pane_id (should be ACTIVE)
        active_lock = Lock(
            task_id="bd-test-active",
            pane_id=pane_id,
            window="test-window",
            agent="test",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(active_lock)

        # Write lock with fake pane_id (should be STALE)
        stale_lock = Lock(
            task_id="bd-test-stale",
            pane_id=fake_pane_id,
            window="test-fake",
            agent="test",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(stale_lock)

        # Evaluate classification
        assert is_active(active_lock, session_name) is True, "Real pane should be ACTIVE"
        assert is_active(stale_lock, session_name) is False, "Fake pane should be STALE"

    finally:
        # Cleanup: remove locks
        from village.config import get_config

        config = get_config()
        for task_id in ["bd-test-active", "bd-test-stale"]:
            lock_path = config.locks_dir / f"{task_id}.lock"
            lock_path.unlink(missing_ok=True)

        # Kill ephemeral session
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            check=False,
        )
