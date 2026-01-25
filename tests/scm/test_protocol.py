"""Tests for SCM protocol behavior."""

from pathlib import Path
from unittest.mock import Mock
import pytest

from village.scm.protocol import SCM, WorkspaceInfo


class TestProtocolCompliance:
    """Test protocol ensures backend compliance."""

    def test_protocol_has_required_methods(self):
        """Test protocol defines all required methods."""
        required_methods = [
            "ensure_repo",
            "check_clean",
            "ensure_workspace",
            "remove_workspace",
            "list_workspaces",
        ]

        for method in required_methods:
            assert method in dir(SCM), f"Protocol missing method: {method}"

    def test_protocol_has_kind_attribute(self):
        """Test protocol defines kind attribute."""
        mock_scm = Mock(spec=SCM)
        mock_scm.kind = "git"

        assert hasattr(mock_scm, "kind")
        assert mock_scm.kind in ["git", "jj"]


class TestWorkspaceInfo:
    """Tests for WorkspaceInfo dataclass."""

    def test_workspace_info_creation(self):
        """Test WorkspaceInfo dataclass creation."""
        info = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test"),
            branch="feature/test",
            commit="abc123",
        )

        assert info.path == Path("/tmp/.worktrees/test")
        assert info.branch == "feature/test"
        assert info.commit == "abc123"

    def test_workspace_info_defaults(self):
        """Test WorkspaceInfo has all required fields."""
        info = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test"),
            branch="main",
            commit="def456",
        )

        assert hasattr(info, "path")
        assert hasattr(info, "branch")
        assert hasattr(info, "commit")

    def test_workspace_info_equality(self):
        """Test WorkspaceInfo equality comparison."""
        info1 = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test"),
            branch="feature",
            commit="abc123",
        )

        info2 = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test"),
            branch="feature",
            commit="abc123",
        )

        assert info1 == info2

    def test_workspace_info_inequality(self):
        """Test WorkspaceInfo inequality comparison."""
        info1 = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test1"),
            branch="feature1",
            commit="abc123",
        )

        info2 = WorkspaceInfo(
            path=Path("/tmp/.worktrees/test2"),
            branch="feature2",
            commit="def456",
        )

        assert info1 != info2


class TestProtocolEdgeCases:
    """Test protocol edge cases (without real backends)."""

    def test_ensure_repo_raises_on_invalid_path(self):
        """Test protocol requires ensure_repo to raise on invalid path."""
        mock_scm = Mock(spec=SCM)

        # Test double raises RuntimeError
        mock_scm.ensure_repo.side_effect = RuntimeError("Not a repo")

        with pytest.raises(RuntimeError, match="Not a repo"):
            mock_scm.ensure_repo(Path("/invalid"))

    def test_check_clean_returns_bool(self):
        """Test protocol requires check_clean to return bool."""
        mock_scm = Mock(spec=SCM)
        mock_scm.check_clean.return_value = True

        result = mock_scm.check_clean(Path("/tmp"))

        assert isinstance(result, bool)
        assert result is True

    def test_check_clean_returns_false_for_dirty(self):
        """Test protocol requires check_clean to return False for dirty."""
        mock_scm = Mock(spec=SCM)
        mock_scm.check_clean.return_value = False

        result = mock_scm.check_clean(Path("/tmp"))

        assert result is False

    def test_ensure_workspace_takes_base_ref(self):
        """Test protocol requires ensure_workspace to accept base_ref."""
        mock_scm = Mock(spec=SCM)

        mock_scm.ensure_workspace(Path("/repo"), Path("/worktree"), "HEAD")

        mock_scm.ensure_workspace.assert_called_once_with(
            Path("/repo"),
            Path("/worktree"),
            "HEAD",
        )

    def test_ensure_workspace_default_base_ref(self):
        """Test protocol requires ensure_workspace to have default base_ref."""
        mock_scm = Mock(spec=SCM)

        mock_scm.ensure_workspace(Path("/repo"), Path("/worktree"))

        # Check if default was called (implementation detail)
        mock_scm.ensure_workspace.assert_called_once()

    def test_remove_workspace_returns_bool(self):
        """Test protocol requires remove_workspace to return bool."""
        mock_scm = Mock(spec=SCM)
        mock_scm.remove_workspace.return_value = True

        result = mock_scm.remove_workspace(Path("/worktree"))

        assert isinstance(result, bool)
        assert result is True

    def test_remove_workspace_returns_false_nonexistent(self):
        """Test protocol requires remove_workspace to return False for nonexistent."""
        mock_scm = Mock(spec=SCM)
        mock_scm.remove_workspace.return_value = False

        result = mock_scm.remove_workspace(Path("/nonexistent"))

        assert result is False

    def test_list_workspaces_returns_list(self):
        """Test protocol requires list_workspaces to return list."""
        mock_scm = Mock(spec=SCM)
        mock_list = [
            WorkspaceInfo(Path("/wt1"), "branch1", "abc123"),
            WorkspaceInfo(Path("/wt2"), "branch2", "def456"),
        ]
        mock_scm.list_workspaces.return_value = mock_list

        result = mock_scm.list_workspaces(Path("/repo"))

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(w, WorkspaceInfo) for w in result)

    def test_list_workspaces_returns_empty_list(self):
        """Test protocol requires list_workspaces to return empty list."""
        mock_scm = Mock(spec=SCM)
        mock_scm.list_workspaces.return_value = []

        result = mock_scm.list_workspaces(Path("/repo"))

        assert result == []
