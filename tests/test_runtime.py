"""Test runtime lifecycle management."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from village.runtime import (
    RuntimeState,
    collect_runtime_state,
    plan_initialization,
    shutdown_runtime,
)


def test_collect_runtime_state():
    """Test state collection when session doesn't exist."""
    subprocess.run(["git", "init"], cwd=Path.cwd(), check=True)
    subprocess.run(["mkdir", "-p", ".village"], cwd=Path.cwd(), check=True)

    with patch("village.probes.tmux.session_exists") as mock_session:
        mock_session.return_value = False

        with patch("village.config.get_config") as mock_config:
            mock_config.return_value = type(
                "Config",
                (),
                {
                    "village_dir": Path.cwd() / ".village",
                    "tmux_session": "village",
                    "beads_dir": Path.cwd() / ".beads",
                },
            )()

            state = collect_runtime_state("village")

            assert state.session_exists is False
            assert state.directories_exist is True
            assert state.beads_initialized is False
            assert state.session_name == "village"


def test_plan_initialization_all_missing():
    """Test planning when nothing exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=False,
            directories_exist=False,
            beads_initialized=False,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is True
        assert plan.needs_directories is True
        assert plan.needs_beads_init is True
        assert plan.session_exists is False
        assert plan.directories_exist is False
        assert plan.beads_initialized is False


def test_plan_initialization_partial():
    """Test planning when session exists but directories don't."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=False,
            beads_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is True
        assert plan.needs_beads_init is False
        assert plan.session_exists is True
        assert plan.directories_exist is False
        assert plan.beads_initialized is True


def test_plan_initialization_idempotent():
    """Test planning when everything exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=True,
            beads_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is False
        assert plan.needs_beads_init is False


def test_shutdown_runtime_success():
    """Test successful session termination."""
    with patch("village.runtime.kill_session") as mock_kill:
        mock_kill.return_value = True

        with patch("village.runtime.session_exists") as mock_exists:
            mock_exists.return_value = True

            success = shutdown_runtime("village")

            assert success is True
            mock_kill.assert_called_once_with("village")


def test_shutdown_runtime_no_session():
    """Test graceful handling when session doesn't exist."""
    with patch("village.probes.tmux.kill_session") as mock_kill:
        mock_kill.return_value = True

    with patch("village.probes.tmux.session_exists") as mock_exists:
        mock_exists.return_value = False

        success = shutdown_runtime("village")

        assert success is True
        mock_kill.assert_not_called()
