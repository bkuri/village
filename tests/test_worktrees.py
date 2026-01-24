"""Tests for workspace management via SCM abstraction."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from village.config import Config
from village.scm import (
    WorkspaceInfo,
    generate_window_name,
    increment_task_id,
    parse_window_name,
)
from village.worktrees import (
    WorktreeInfo,
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


@pytest.fixture
def mock_scm() -> Generator[Mock, None, None]:
    """Mock SCM backend."""
    scm_mock = Mock()
    scm_mock.kind = "git"
    scm_mock.check_clean.return_value = True
    scm_mock.ensure_workspace.return_value = None
    scm_mock.remove_workspace.return_value = True
    scm_mock.list_workspaces.return_value = []
    with patch("village.worktrees.get_scm", return_value=scm_mock):
        yield scm_mock


class TestGetWorktreePath:
    """Tests for get_worktree_path."""

    def test_resolves_to_worktrees_dir(self, mock_config: Config) -> None:
        """Test that path resolves to worktrees_dir/task_id."""
        task_id = "bd-a3f8"
        path = get_worktree_path(task_id, mock_config)
        assert path == mock_config.worktrees_dir / task_id


class TestCreateWorktree:
    """Tests for create_worktree."""

    def test_creates_workspace_successfully(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test successful workspace creation."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.scm.utils.generate_window_name", return_value=f"worker-1-{task_id}"):
            result = create_worktree(task_id, session_name, mock_config)

            path, window_name = result
            assert path == mock_config.worktrees_dir / task_id
            assert window_name == f"worker-1-{task_id}"

            # Verify SCM methods called
            mock_scm.check_clean.assert_called_once_with(mock_config.git_root)
            mock_scm.ensure_workspace.assert_called_once()
            call_args = mock_scm.ensure_workspace.call_args
            assert call_args[0][0] == mock_config.git_root
            assert call_args[0][1] == mock_config.worktrees_dir / task_id
            assert call_args[0][2] == f"worktree-{task_id}"

    def test_fails_on_dirty_repo(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that dirty repo raises error."""
        task_id = "bd-a3f8"
        session_name = "village"

        mock_scm.check_clean.return_value = False

        with pytest.raises(RuntimeError, match="uncommitted changes"):
            create_worktree(task_id, session_name, mock_config)

    def test_fails_on_scm_error(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that SCM errors are raised."""
        task_id = "bd-a3f8"
        session_name = "village"

        mock_scm.ensure_workspace.side_effect = RuntimeError("Failed to create workspace")

        with pytest.raises(RuntimeError, match="Failed to create workspace"):
            create_worktree(task_id, session_name, mock_config)


class TestDeleteWorktree:
    """Tests for delete_worktree."""

    def test_deletes_existing_workspace(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test successful workspace deletion."""
        task_id = "bd-a3f8"

        mock_scm.remove_workspace.return_value = True

        result = delete_worktree(task_id, mock_config)

        assert result is True

        # Verify SCM method called
        mock_scm.remove_workspace.assert_called_once_with(mock_config.worktrees_dir / task_id)

    def test_returns_false_for_nonexistent_workspace(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that nonexistent workspace returns False."""
        task_id = "bd-a3f8"

        mock_scm.remove_workspace.return_value = False

        result = delete_worktree(task_id, mock_config)

        assert result is False


class TestListWorktrees:
    """Tests for list_worktrees."""

    def test_lists_all_workspaces(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test listing workspaces."""
        workspace1 = WorkspaceInfo(
            path=mock_config.worktrees_dir / "bd-a3f8",
            branch="refs/heads/worktree-bd-a3f8",
            commit="def456",
        )
        workspace2 = WorkspaceInfo(
            path=mock_config.worktrees_dir / "bd-b2c4",
            branch="refs/heads/worktree-bd-b2c4",
            commit="ghi789",
        )

        mock_scm.list_workspaces.return_value = [workspace1, workspace2]

        worktrees = list_worktrees(mock_config)

        assert len(worktrees) == 2
        assert worktrees[0].task_id == "bd-a3f8"
        assert worktrees[1].task_id == "bd-b2c4"
        assert worktrees[0].branch == "refs/heads/worktree-bd-a3f8"
        assert worktrees[1].branch == "refs/heads/worktree-bd-b2c4"

    def test_ignores_non_village_workspaces(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that non-village workspaces are filtered out."""
        workspace = WorkspaceInfo(
            path=Path("/tmp/other-workspace"),
            branch="refs/heads/other-branch",
            commit="def456",
        )

        mock_scm.list_workspaces.return_value = [workspace]

        worktrees = list_worktrees(mock_config)

        assert len(worktrees) == 0

    def test_handles_detached_workspaces(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that detached workspaces are handled correctly."""
        workspace = WorkspaceInfo(
            path=mock_config.worktrees_dir / "bd-a3f8",
            branch="(detached)",
            commit="def456",
        )

        mock_scm.list_workspaces.return_value = [workspace]

        worktrees = list_worktrees(mock_config)

        assert len(worktrees) == 1
        assert worktrees[0].task_id == "bd-a3f8"
        assert worktrees[0].branch == "(detached)"


class TestGetWorktreeInfo:
    """Tests for get_worktree_info."""

    def test_returns_info_for_existing_workspace(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test getting info for existing workspace."""
        task_id = "bd-a3f8"
        workspace = WorkspaceInfo(
            path=mock_config.worktrees_dir / task_id,
            branch="refs/heads/worktree-bd-a3f8",
            commit="def456",
        )

        mock_scm.list_workspaces.return_value = [workspace]

        info = get_worktree_info(task_id, mock_config)

        assert info is not None
        assert info.task_id == task_id
        assert info.branch == "refs/heads/worktree-bd-a3f8"

    def test_returns_none_for_nonexistent_workspace(
        self,
        mock_config: Config,
        mock_scm: Mock,
    ) -> None:
        """Test that nonexistent workspace returns None."""
        task_id = "bd-a3f8"

        mock_scm.list_workspaces.return_value = []

        info = get_worktree_info(task_id, mock_config)

        assert info is None


class TestWorkspaceNamingHelpers:
    """Tests for workspace naming helper functions."""

    def test_generate_window_name(self) -> None:
        """Test window name generation."""
        task_id = "bd-a3f8"

        window_name = generate_window_name(task_id, 1)

        assert window_name == f"worker-1-{task_id}"

    def test_parse_window_name_valid(self) -> None:
        """Test parsing valid window name."""
        window_name = "build-1-bd-a3f8"

        parts = parse_window_name(window_name)

        assert parts["agent"] == "build"
        assert parts["worker_num"] == "1"
        assert parts["task_id"] == "bd-a3f8"

    def test_parse_window_name_invalid(self) -> None:
        """Test parsing invalid window name."""
        window_name = "invalid-name"

        parts = parse_window_name(window_name)

        assert parts == {}

    def test_increment_task_id(self) -> None:
        """Test task ID increment."""
        task_id = "bd-a3f8"

        incremented = increment_task_id(task_id, 2)

        assert incremented == "bd-a3f8-2"

        incremented = increment_task_id(task_id, 3)

        assert incremented == "bd-a3f8-3"


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
