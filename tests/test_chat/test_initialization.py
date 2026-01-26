"""Test Beads initialization for chat mode."""

from pathlib import Path
from unittest.mock import patch

from village.chat.initialization import ensure_beads_initialized, is_beads_available
from village.config import Config
from village.probes.tools import SubprocessError


def test_ensure_beads_initialized_no_beads_dir(tmp_path: Path, mock_config: Config) -> None:
    """
    Test that function returns early when .beads directory doesn't exist.

    Verify that no bd commands are called when .beads/ is missing.
    """
    # Ensure .beads directory doesn't exist
    assert not (mock_config.git_root / ".beads").exists()

    with patch("village.chat.initialization.run_command_output") as mock_run:
        ensure_beads_initialized(mock_config)

        # Verify no bd commands were called
        mock_run.assert_not_called()


def test_ensure_beads_initialized_config_has_draft_status(
    tmp_path: Path, mock_config: Config
) -> None:
    """
    Test that function returns early when status.custom already contains 'draft'.

    Verify that no config modification occurs when draft status is already set.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to show status.custom exists
        # Mock bd config get to return "draft"
        def side_effect(cmd: list[str]) -> str:
            if cmd == ["bd", "config", "list"]:
                return "status.custom=draft"
            elif cmd == ["bd", "config", "get", "status.custom"]:
                return "draft"
            raise ValueError(f"Unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        ensure_beads_initialized(mock_config)

        # Verify bd config list was called
        mock_run.assert_any_call(["bd", "config", "list"])

        # Verify bd config get was called
        mock_run.assert_any_call(["bd", "config", "get", "status.custom"])

        # Verify bd config set was NOT called
        set_calls = [
            call
            for call in mock_run.call_args_list
            if call[0][0] == ["bd", "config", "set", "status.custom", "draft"]
        ]
        assert len(set_calls) == 0


def test_ensure_beads_initialized_config_missing_draft(tmp_path: Path, mock_config: Config) -> None:
    """
    Test that function configures draft status when it's missing.

    Verify that bd config set command is called when status is not configured.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to show status.custom doesn't exist
        # Mock bd config set to succeed
        def side_effect(cmd: list[str]) -> str:
            if cmd == ["bd", "config", "list"]:
                return ""
            elif cmd == ["bd", "config", "set", "status.custom", "draft"]:
                return ""
            raise ValueError(f"Unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        ensure_beads_initialized(mock_config)

        # Verify bd config list was called
        mock_run.assert_any_call(["bd", "config", "list"])

        # Verify bd config set was called
        mock_run.assert_any_call(["bd", "config", "set", "status.custom", "draft"])


def test_ensure_beads_initialized_config_has_other_status(
    tmp_path: Path, mock_config: Config
) -> None:
    """
    Test that function configures draft status when status.custom has other values.

    Verify that bd config set is called even when status.custom exists but doesn't contain 'draft'.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to show status.custom exists with other values
        # Mock bd config get to return other statuses
        # Mock bd config set to succeed
        def side_effect(cmd: list[str]) -> str:
            if cmd == ["bd", "config", "list"]:
                return "status.custom=ready,blocked"
            elif cmd == ["bd", "config", "get", "status.custom"]:
                return "ready,blocked"
            elif cmd == ["bd", "config", "set", "status.custom", "draft"]:
                return ""
            raise ValueError(f"Unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        ensure_beads_initialized(mock_config)

        # Verify bd config list was called
        mock_run.assert_any_call(["bd", "config", "list"])

        # Verify bd config get was called
        mock_run.assert_any_call(["bd", "config", "get", "status.custom"])

        # Verify bd config set was called
        mock_run.assert_any_call(["bd", "config", "set", "status.custom", "draft"])


def test_ensure_beads_initialized_config_has_draft_in_list(
    tmp_path: Path, mock_config: Config
) -> None:
    """
    Test that function returns early when 'draft' is among multiple statuses.

    Verify no config modification when draft exists in comma-separated status list.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to show status.custom exists
        # Mock bd config get to return statuses including 'draft'
        def side_effect(cmd: list[str]) -> str:
            if cmd == ["bd", "config", "list"]:
                return "status.custom=ready,draft,blocked"
            elif cmd == ["bd", "config", "get", "status.custom"]:
                return "ready,draft,blocked"
            raise ValueError(f"Unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        ensure_beads_initialized(mock_config)

        # Verify bd config list was called
        mock_run.assert_any_call(["bd", "config", "list"])

        # Verify bd config get was called
        mock_run.assert_any_call(["bd", "config", "get", "status.custom"])

        # Verify bd config set was NOT called
        set_calls = [
            call
            for call in mock_run.call_args_list
            if call[0][0] == ["bd", "config", "set", "status.custom", "draft"]
        ]
        assert len(set_calls) == 0


def test_ensure_beads_initialized_beads_command_fails(tmp_path: Path, mock_config: Config) -> None:
    """
    Test that function handles SubprocessError gracefully.

    Verify function continues without crashing when bd commands fail.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to fail
        mock_run.side_effect = SubprocessError("bd command failed")

        # Should not raise exception
        ensure_beads_initialized(mock_config)

        # Verify bd command was attempted
        mock_run.assert_called_once_with(["bd", "config", "list"])


def test_ensure_beads_initialized_general_exception(tmp_path: Path, mock_config: Config) -> None:
    """
    Test that function handles general exceptions gracefully.

    Verify function continues without crashing when unexpected errors occur.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    with patch("village.chat.initialization.run_command_output") as mock_run:
        # Mock bd config list to raise general exception
        mock_run.side_effect = RuntimeError("Unexpected error")

        # Should not raise exception
        ensure_beads_initialized(mock_config)

        # Verify bd command was attempted
        mock_run.assert_called_once_with(["bd", "config", "list"])


def test_is_beads_available_with_beads_dir(tmp_path: Path, mock_config: Config) -> None:
    """
    Test is_beads_available returns True when .beads directory exists.
    """
    # Create mock .beads directory
    beads_dir = mock_config.git_root / ".beads"
    beads_dir.mkdir(parents=True, exist_ok=True)

    result = is_beads_available(mock_config)

    assert result is True


def test_is_beads_available_without_beads_dir(tmp_path: Path, mock_config: Config) -> None:
    """
    Test is_beads_available returns False when .beads directory doesn't exist.
    """
    # Ensure .beads directory doesn't exist
    assert not (mock_config.git_root / ".beads").exists()

    result = is_beads_available(mock_config)

    assert result is False
