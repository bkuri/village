"""Tests for GitSCM backend implementation."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from village.probes.tools import SubprocessError
from village.scm.git import GitSCM
from village.scm.protocol import WorkspaceInfo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True
    )

    (repo_dir / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"], cwd=repo_dir, check=True, capture_output=True
    )

    return repo_dir


@pytest.fixture
def git_scm() -> GitSCM:
    """Create GitSCM instance."""
    return GitSCM()


class TestGitSCMProperties:
    """Tests for GitSCM properties."""

    def test_git_scm_kind(self, git_scm: GitSCM) -> None:
        """Test GitSCM has correct kind."""
        assert git_scm.kind == "git"


class TestGitSCMEnsureRepo:
    """Tests for ensure_repo method."""

    def test_ensure_repo_valid_git_repo(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_repo succeeds for valid Git repository."""
        git_scm.ensure_repo(git_repo)

    def test_ensure_repo_raises_for_non_repo(self, tmp_path: Path, git_scm: GitSCM) -> None:
        """Test ensure_repo raises RuntimeError for non-Git directory."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()

        with pytest.raises(RuntimeError, match="Not a Git repository"):
            git_scm.ensure_repo(non_repo)

    def test_ensure_repo_raises_for_subdir(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_repo raises for subdirectory of repo."""
        subdir = git_repo / "subdir"
        subdir.mkdir()

        with pytest.raises(RuntimeError, match="not a Git repository root"):
            git_scm.ensure_repo(subdir)

    def test_ensure_repo_handles_git_command_failure(self, git_scm: GitSCM) -> None:
        """Test ensure_repo handles Git command failure."""
        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("Git command failed")

            with pytest.raises(RuntimeError, match="Not a Git repository"):
                git_scm.ensure_repo(Path("/invalid"))


class TestGitSCMCheckClean:
    """Tests for check_clean method."""

    def test_check_clean_clean_repo(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test check_clean returns True for clean repository."""
        assert git_scm.check_clean(git_repo) is True

    def test_check_clean_dirty_repo(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test check_clean returns False for dirty repository."""
        (git_repo / "README.md").write_text("# Modified")

        assert git_scm.check_clean(git_repo) is False

    def test_check_clean_untracked_file(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test check_clean returns False for untracked file."""
        (git_repo / "newfile.txt").write_text("content")

        assert git_scm.check_clean(git_repo) is False

    def test_check_clean_staged_file(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test check_clean returns False for staged file."""
        (git_repo / "README.md").write_text("# Modified")
        subprocess.run(["git", "add", "README.md"], cwd=git_repo, check=True, capture_output=True)

        assert git_scm.check_clean(git_repo) is False

    def test_check_clean_handles_git_error(self, git_scm: GitSCM) -> None:
        """Test check_clean raises RuntimeError on Git error."""
        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("Git failed")

            with pytest.raises(RuntimeError, match="Failed to check repository status"):
                git_scm.check_clean(Path("/invalid"))


class TestGitSCMEnsureWorkspace:
    """Tests for ensure_workspace method."""

    def test_ensure_workspace_creates_worktree(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_workspace creates Git worktree."""
        worktree_path = git_repo.parent / "worktrees" / "test-branch"

        git_scm.ensure_workspace(git_repo, worktree_path, "test-branch")

        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()

    def test_ensure_workspace_creates_branch(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_workspace creates new branch."""
        worktree_path = git_repo.parent / "worktrees" / "feature"

        git_scm.ensure_workspace(git_repo, worktree_path, "feature")

        result = subprocess.run(
            ["git", "branch", "--list", "feature"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "feature" in result.stdout

    def test_ensure_workspace_creates_from_branch(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_workspace creates worktree from existing branch."""
        subprocess.run(
            ["git", "branch", "test-base"], cwd=git_repo, check=True, capture_output=True
        )

        worktree_path = git_repo.parent / "worktrees" / "test-branch"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "test-base"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        assert worktree_path.exists()

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "test-base"

    def test_ensure_workspace_default_base_ref(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_workspace creates worktree on a new branch."""
        worktree_path = git_repo.parent / "worktrees" / "default-branch"
        git_scm.ensure_workspace(git_repo, worktree_path, "default-branch")

        assert worktree_path.exists()

        result = subprocess.run(
            ["git", "branch", "--list", "default-branch"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "default-branch" in result.stdout

    def test_ensure_workspace_existing_worktree_error(
        self, git_repo: Path, git_scm: GitSCM
    ) -> None:
        """Test ensure_workspace raises for existing worktree."""
        worktree_path = git_repo.parent / "worktrees" / "existing"

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "existing"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        with pytest.raises(RuntimeError, match="Failed to create worktree"):
            git_scm.ensure_workspace(git_repo, worktree_path, "existing")

    def test_ensure_workspace_handles_git_failure(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test ensure_workspace handles Git command failure."""
        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("Git worktree add failed")

            worktree_path = git_repo.parent / "worktrees" / "fail"

            with pytest.raises(RuntimeError, match="Failed to create worktree"):
                git_scm.ensure_workspace(git_repo, worktree_path, "fail-branch")


class TestGitSCMRemoveWorkspace:
    """Tests for remove_workspace method."""

    def test_remove_workspace_removes_worktree(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test remove_workspace removes Git worktree."""
        worktree_path = git_repo.parent / "worktrees" / "test"
        git_scm.ensure_workspace(git_repo, worktree_path, "test")

        removed = git_scm.remove_workspace(worktree_path)

        assert removed is True
        assert not worktree_path.exists()

    def test_remove_workspace_nonexistent_returns_false(
        self, git_scm: GitSCM, tmp_path: Path
    ) -> None:
        """Test remove_workspace returns False for nonexistent worktree."""
        nonexistent = tmp_path / "nonexistent"

        removed = git_scm.remove_workspace(nonexistent)

        assert removed is False

    def test_remove_workspace_removes_from_git_registry(
        self, git_repo: Path, git_scm: GitSCM
    ) -> None:
        """Test remove_workspace removes worktree from Git registry."""
        worktree_path = git_repo.parent / "worktrees" / "test"
        git_scm.ensure_workspace(git_repo, worktree_path, "test")

        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert str(worktree_path) in result.stdout

        git_scm.remove_workspace(worktree_path)

        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert str(worktree_path) not in result.stdout


class TestGitSCMListWorkspaces:
    """Tests for list_workspaces method."""

    def test_list_workspaces_no_worktrees(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces returns main repo when no additional worktrees."""
        workspaces = git_scm.list_workspaces(git_repo)

        assert len(workspaces) == 1
        assert workspaces[0].path == git_repo

    def test_list_workspaces_single_worktree(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces returns main repo plus single worktree."""
        worktree_path = git_repo.parent / "worktrees" / "branch1"
        git_scm.ensure_workspace(git_repo, worktree_path, "branch1")

        workspaces = git_scm.list_workspaces(git_repo)

        assert len(workspaces) == 2
        assert any(w.path == worktree_path for w in workspaces)
        assert any(w.path == git_repo for w in workspaces)
        assert all(isinstance(w, WorkspaceInfo) for w in workspaces)

    def test_list_workspaces_multiple_worktrees(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces returns multiple worktrees."""
        worktree1 = git_repo.parent / "worktrees" / "branch1"
        worktree2 = git_repo.parent / "worktrees" / "branch2"

        git_scm.ensure_workspace(git_repo, worktree1, "branch1")
        git_scm.ensure_workspace(git_repo, worktree2, "branch2")

        workspaces = git_scm.list_workspaces(git_repo)

        assert len(workspaces) == 3
        assert any(w.path == worktree1 for w in workspaces)
        assert any(w.path == worktree2 for w in workspaces)
        assert any(w.path == git_repo for w in workspaces)

    def test_list_workspaces_includes_branch_info(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces includes branch information."""
        worktree_path = git_repo.parent / "worktrees" / "feature"
        git_scm.ensure_workspace(git_repo, worktree_path, "feature")

        workspaces = git_scm.list_workspaces(git_repo)

        assert len(workspaces) == 2

        feature_ws = next(w for w in workspaces if w.path == worktree_path)
        assert feature_ws.path == worktree_path
        assert feature_ws.branch is not None
        assert feature_ws.commit is not None

    def test_list_workspaces_handles_git_error(self, git_scm: GitSCM) -> None:
        """Test list_workspaces handles Git command error."""
        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("Git failed")

            with pytest.raises(RuntimeError, match="Failed to list worktrees"):
                git_scm.list_workspaces(Path("/invalid"))

    def test_list_workspaces_detached_head(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces handles detached HEAD worktrees."""
        worktree_path = git_repo.parent / "worktrees" / "detached"

        commit_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        ).stdout.strip()

        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), commit_hash],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        workspaces = git_scm.list_workspaces(git_repo)

        assert len(workspaces) == 2

        detached_ws = next(w for w in workspaces if w.path == worktree_path)
        assert detached_ws.path == worktree_path
        assert detached_ws.branch == "(detached)"
        assert detached_ws.commit is not None

    def test_list_workspaces_skips_nonexistent_paths(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test list_workspaces skips worktrees with nonexistent paths."""
        worktree_path = git_repo.parent / "worktrees" / "ghost"
        git_scm.ensure_workspace(git_repo, worktree_path, "ghost")

        workspaces = git_scm.list_workspaces(git_repo)
        assert len(workspaces) == 2

        subprocess.run(["rm", "-rf", str(worktree_path)], check=True)

        workspaces = git_scm.list_workspaces(git_repo)
        assert len(workspaces) == 1
        assert workspaces[0].path == git_repo


class TestGitSCMRemoveWorkspaceErrorHandling:
    """Tests for remove_workspace error handling."""

    def test_remove_workspace_handles_git_error(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test remove_workspace raises RuntimeError on git failure."""
        worktree_path = git_repo.parent / "worktrees" / "fail"
        git_scm.ensure_workspace(git_repo, worktree_path, "fail")

        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("git worktree remove failed")

            with pytest.raises(RuntimeError, match="Failed to remove worktree"):
                git_scm.remove_workspace(worktree_path)


class TestGitSCMResetWorkspace:
    """Tests for reset_workspace method."""

    def test_reset_workspace_discards_changes(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test reset_workspace discards all modifications."""
        worktree_path = git_repo.parent / "worktrees" / "reset-test"
        git_scm.ensure_workspace(git_repo, worktree_path, "reset-test")

        test_file = worktree_path / "test.txt"
        test_file.write_text("original content")
        subprocess.run(
            ["git", "add", "test.txt"], cwd=worktree_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add test file"],
            cwd=worktree_path,
            check=True,
            capture_output=True,
        )

        test_file.write_text("modified content")

        untracked = worktree_path / "untracked.txt"
        untracked.write_text("untracked")

        git_scm.reset_workspace(worktree_path)

        assert test_file.read_text() == "original content"
        assert not untracked.exists()

    def test_reset_workspace_removes_untracked_dirs(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test reset_workspace removes untracked directories."""
        worktree_path = git_repo.parent / "worktrees" / "reset-dirs"
        git_scm.ensure_workspace(git_repo, worktree_path, "reset-dirs")

        untracked_dir = worktree_path / "untracked_dir"
        untracked_dir.mkdir()
        (untracked_dir / "file.txt").write_text("content")

        git_scm.reset_workspace(worktree_path)

        assert not untracked_dir.exists()

    def test_reset_workspace_raises_for_nonexistent_path(
        self, git_scm: GitSCM, tmp_path: Path
    ) -> None:
        """Test reset_workspace raises RuntimeError for nonexistent worktree."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(RuntimeError, match="Worktree does not exist"):
            git_scm.reset_workspace(nonexistent)

    def test_reset_workspace_handles_git_error(self, git_repo: Path, git_scm: GitSCM) -> None:
        """Test reset_workspace handles git command failure."""
        worktree_path = git_repo.parent / "worktrees" / "reset-fail"
        git_scm.ensure_workspace(git_repo, worktree_path, "reset-fail")

        with patch("village.scm.git.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("git reset failed")

            with pytest.raises(RuntimeError, match="Failed to reset worktree"):
                git_scm.reset_workspace(worktree_path)
