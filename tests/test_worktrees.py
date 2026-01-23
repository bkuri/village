"""Tests for worktree management."""

import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from village.config import Config, get_config
from village.probes.tools import SubprocessError
from village.worktrees import (
    WorktreeInfo,
    _generate_window_name,
    _increment_worker_num,
    _parse_window_name,
    create_worktree,
    delete_worktree,
    get_worktree_info,
    get_worktree_path,
    list_worktrees,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config."""
    return Config(
        git_root=tmp_path / "repo",
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )


@pytest.fixture
def mock_get_config(mock_config: Config) -> Generator[None, None, None]:
    """Mock get_config function."""
    with patch("village.worktrees.get_config", return_value=mock_config):
        yield


class TestGetWorktreePath:
    """Tests for get_worktree_path."""

    def test_resolves_to_worktrees_dir(self, mock_config: Config) -> None:
        """Test that path resolves to worktrees_dir/task_id."""
        task_id = "bd-a3f8"
        path = get_worktree_path(task_id, mock_config)
        assert path == mock_config.worktrees_dir / task_id


class TestCreateWorktree:
    """Tests for create_worktree."""

    def test_creates_worktree_successfully(
        self,
        mock_config: Config,
    ) -> None:
        """Test successful worktree creation."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.worktrees.run_command") as mock_run:
            with patch("village.worktrees._check_git_dirty"):
                result = create_worktree(task_id, session_name, mock_config)

                path, window_name = result
                assert path == mock_config.worktrees_dir / task_id
                assert window_name == f"worker-1-{task_id}"

                # Verify git worktree add command
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "git"
                assert cmd[1] == "worktree"
                assert cmd[2] == "add"
                assert str(mock_config.worktrees_dir / task_id) in cmd
                assert "-b" in cmd
                assert f"worktree-{task_id}" in cmd

    def test_fails_on_dirty_repo(
        self,
        mock_config: Config,
    ) -> None:
        """Test that dirty repo raises error."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.worktrees._check_git_dirty") as mock_check:
            mock_check.side_effect = RuntimeError("Repository has uncommitted changes")

            with pytest.raises(RuntimeError, match="uncommitted changes"):
                create_worktree(task_id, session_name, mock_config)

    def test_fails_on_git_error(
        self,
        mock_config: Config,
    ) -> None:
        """Test that git errors are raised."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.worktrees.run_command") as mock_run:
            with patch("village.worktrees._check_git_dirty"):
                mock_run.side_effect = SubprocessError("git worktree failed")

                with pytest.raises(SubprocessError, match="git worktree failed"):
                    create_worktree(task_id, session_name, mock_config)


class TestDeleteWorktree:
    """Tests for delete_worktree."""

    def test_deletes_existing_worktree(
        self,
        mock_config: Config,
    ) -> None:
        """Test successful worktree deletion."""
        task_id = "bd-a3f8"

        with patch("village.worktrees.run_command") as mock_run:
            with patch.object(Path, "exists", return_value=True):
                result = delete_worktree(task_id, mock_config)

                assert result is True

                # Verify git worktree remove command
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "git"
                assert cmd[1] == "worktree"
                assert cmd[2] == "remove"

    def test_returns_false_for_nonexistent_worktree(
        self,
        mock_config: Config,
    ) -> None:
        """Test that nonexistent worktree returns False."""
        task_id = "bd-a3f8"

        # Worktree path doesn't exist
        result = delete_worktree(task_id, mock_config)
        assert result is False


class TestListWorktrees:
    """Tests for list_worktrees."""

    def test_lists_all_worktrees(
        self,
        mock_config: Config,
    ) -> None:
        """Test listing worktrees."""
        output = f"""worktree {mock_config.git_root}
HEAD abc123
branch refs/heads/main

worktree {mock_config.worktrees_dir / "bd-a3f8"}
HEAD def456
branch refs/heads/worktree-bd-a3f8

worktree {mock_config.worktrees_dir / "bd-b2c4"}
HEAD ghi789
branch refs/heads/worktree-bd-b2c4
"""

        with patch("village.worktrees.run_command_output") as mock_run:
            mock_run.return_value = output

            worktrees = list_worktrees(mock_config)

            assert len(worktrees) == 2
            assert worktrees[0].task_id == "bd-a3f8"
            assert worktrees[1].task_id == "bd-b2c4"
            assert worktrees[0].branch == "refs/heads/worktree-bd-a3f8"
            assert worktrees[1].branch == "refs/heads/worktree-bd-b2c4"

    def test_ignores_non_village_worktrees(
        self,
        mock_config: Config,
    ) -> None:
        """Test that non-village worktrees are filtered out."""
        output = f"""worktree {mock_config.git_root}
HEAD abc123
branch refs/heads/main

worktree /tmp/other-worktree
HEAD def456
branch refs/heads/other-branch
"""

        with patch("village.worktrees.run_command_output") as mock_run:
            mock_run.return_value = output

            worktrees = list_worktrees(mock_config)

            assert len(worktrees) == 0

    def test_handles_detached_worktrees(
        self,
        mock_config: Config,
    ) -> None:
        """Test that detached worktrees are handled correctly."""
        output = f"""worktree {mock_config.worktrees_dir / "bd-a3f8"}
HEAD def456
detached
"""

        with patch("village.worktrees.run_command_output") as mock_run:
            mock_run.return_value = output

            worktrees = list_worktrees(mock_config)

            assert len(worktrees) == 1
            assert worktrees[0].task_id == "bd-a3f8"
            assert worktrees[0].branch == "(detached)"


class TestGetWorktreeInfo:
    """Tests for get_worktree_info."""

    def test_returns_info_for_existing_worktree(
        self,
        mock_config: Config,
    ) -> None:
        """Test getting info for existing worktree."""
        task_id = "bd-a3f8"
        output = f"""worktree {mock_config.worktrees_dir / task_id}
HEAD def456
branch refs/heads/worktree-bd-a3f8
"""

        with patch("village.worktrees.run_command_output") as mock_run:
            mock_run.return_value = output

            info = get_worktree_info(task_id, mock_config)

            assert info is not None
            assert info.task_id == task_id
            assert info.branch == "refs/heads/worktree-bd-a3f8"

    def test_returns_none_for_nonexistent_worktree(
        self,
        mock_config: Config,
    ) -> None:
        """Test that nonexistent worktree returns None."""
        task_id = "bd-a3f8"
        output = ""

        with patch("village.worktrees.run_command_output") as mock_run:
            mock_run.return_value = output

            info = get_worktree_info(task_id, mock_config)

            assert info is None


class TestWindowNamingHelpers:
    """Tests for window naming helper functions."""

    def test_generate_window_name(self) -> None:
        """Test window name generation."""
        task_id = "bd-a3f8"
        session_name = "village"

        window_name = _generate_window_name(task_id, session_name)

        assert window_name == f"worker-1-{task_id}"

    def test_parse_window_name_valid(self) -> None:
        """Test parsing valid window name."""
        window_name = "build-1-bd-a3f8"

        parts = _parse_window_name(window_name)

        assert parts["agent"] == "build"
        assert parts["worker_num"] == "1"
        assert parts["task_id"] == "bd-a3f8"

    def test_parse_window_name_invalid(self) -> None:
        """Test parsing invalid window name."""
        window_name = "invalid-name"

        parts = _parse_window_name(window_name)

        assert parts == {}

    def test_increment_worker_num(self) -> None:
        """Test worker number increment."""
        task_id = "bd-a3f8"

        incremented = _increment_worker_num(task_id, 2)

        assert incremented == "bd-a3f8-2"

        incremented = _increment_worker_num(task_id, 3)

        assert incremented == "bd-a3f8-3"


class TestCheckGitDirty:
    """Tests for _check_git_dirty."""

    def test_raises_error_on_dirty_repo(
        self,
        mock_config: Config,
    ) -> None:
        """Test that dirty repo raises error."""
        with patch("village.worktrees.run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["git", "status", "--porcelain"],
                returncode=0,
                stdout=" M file.txt\n",
                stderr="",
            )

            with pytest.raises(RuntimeError, match="uncommitted changes"):
                from village.worktrees import _check_git_dirty

                _check_git_dirty(mock_config.git_root)

    def test_passes_on_clean_repo(
        self,
        mock_config: Config,
    ) -> None:
        """Test that clean repo passes."""
        with patch("village.worktrees.run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["git", "status", "--porcelain"],
                returncode=0,
                stdout="",
                stderr="",
            )

            from village.worktrees import _check_git_dirty

            _check_git_dirty(mock_config.git_root)


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_worktree_info_creation(self) -> None:
        """Test WorktreeInfo creation."""
        info = WorktreeInfo(
            task_id="bd-a3f8",
            path=Path("/tmp/.worktrees/bd-a3f8"),
            branch="refs/heads/worktree-bd-a3f8",
            commit="abc123",
        )

        assert info.task_id == "bd-a3f8"
        assert info.path == Path("/tmp/.worktrees/bd-a3f8")
        assert info.branch == "refs/heads/worktree-bd-a3f8"
        assert info.commit == "abc123"
