"""Tests for GitHub integration module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from village.github_integration import (
    GitHubError,
    PRDescription,
    SyncResult,
    _generate_changes_summary,
    _generate_commit_suggestions,
    _generate_summary,
    _generate_testing_checklist,
    _get_git_diff,
    _get_task_metadata,
    _parse_file_changes,
    _run_gh_command,
    add_pr_labels,
    create_pr,
    generate_pr_description,
    sync_pr_status,
)


@pytest.fixture
def mock_worktree_path(tmp_path: Path) -> Path:
    """Create a mock worktree path."""
    worktree = tmp_path / ".worktrees" / "bd-a3f8"
    worktree.mkdir(parents=True)
    return worktree


@pytest.fixture
def mock_git_diff_output():
    """Mock git diff output."""
    return """A\tvillage/new_file.py
M\tvillage/existing.py
D\tvillage/old_file.py
R100\tvillage/old_name.py\tvillage/new_name.py"""


class TestRunGhCommand:
    """Tests for _run_gh_command function."""

    @patch("village.github_integration.subprocess.run")
    def test_runs_gh_command_successfully(self, mock_run):
        """Test successful gh command execution."""
        mock_run.return_value = subprocess.CompletedProcess(
            ["gh", "pr", "view", "123"],
            returncode=0,
            stdout="PR output",
            stderr="",
        )

        result = _run_gh_command(["pr", "view", "123"])

        assert result == "PR output"
        mock_run.assert_called_once()

    @patch("village.github_integration.subprocess.run")
    def test_raises_on_command_failure(self, mock_run):
        """Test exception raised on command failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["gh", "pr", "view"], stderr="PR not found"
        )

        with pytest.raises(GitHubError, match="gh command failed"):
            _run_gh_command(["pr", "view", "123"])

    @patch("village.github_integration.subprocess.run")
    def test_raises_on_gh_not_installed(self, mock_run):
        """Test exception raised when gh not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(GitHubError, match="GitHub CLI.*not installed"):
            _run_gh_command(["pr", "view", "123"])


class TestGetGitDiff:
    """Tests for _get_git_diff function."""

    @patch("village.github_integration.subprocess.run")
    def test_gets_git_diff_successfully(self, mock_run, mock_worktree_path):
        """Test successful git diff."""
        mock_run.return_value = subprocess.CompletedProcess(
            ["git", "diff", "HEAD", "--name-status"],
            returncode=0,
            stdout="M\tfile.py",
            stderr="",
        )

        result = _get_git_diff(mock_worktree_path)

        assert result == "M\tfile.py"
        mock_run.assert_called_once_with(
            ["git", "diff", "HEAD", "--name-status"],
            cwd=mock_worktree_path,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )

    @patch("village.github_integration.subprocess.run")
    def test_raises_on_git_failure(self, mock_run, mock_worktree_path):
        """Test exception raised on git failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["git", "diff"], stderr="Not a git repository"
        )

        with pytest.raises(GitHubError, match="git diff failed"):
            _get_git_diff(mock_worktree_path)


class TestParseFileChanges:
    """Tests for _parse_file_changes function."""

    def test_parses_added_files(self):
        """Test parsing added files."""
        diff = "A\tnew_file.py\nA\tanother.py"
        result = _parse_file_changes(diff)

        assert result["added"] == ["new_file.py", "another.py"]
        assert result["modified"] == []
        assert result["deleted"] == []
        assert result["renamed"] == []

    def test_parses_modified_files(self):
        """Test parsing modified files."""
        diff = "M\tmodified.py\nM\tchanged.py"
        result = _parse_file_changes(diff)

        assert result["added"] == []
        assert result["modified"] == ["modified.py", "changed.py"]
        assert result["deleted"] == []
        assert result["renamed"] == []

    def test_parses_deleted_files(self):
        """Test parsing deleted files."""
        diff = "D\tdeleted.py\nD\tremoved.py"
        result = _parse_file_changes(diff)

        assert result["added"] == []
        assert result["modified"] == []
        assert result["deleted"] == ["deleted.py", "removed.py"]
        assert result["renamed"] == []

    def test_parses_renamed_files(self):
        """Test parsing renamed files."""
        diff = "R100\told.py\tnew.py"
        result = _parse_file_changes(diff)

        assert result["added"] == []
        assert result["modified"] == []
        assert result["deleted"] == []
        assert result["renamed"] == ["new.py"]

    def test_parses_mixed_changes(self):
        """Test parsing mixed file changes."""
        diff = """A\tnew.py
M\tmodified.py
D\tdeleted.py
R100\told.py\trenamed.py"""
        result = _parse_file_changes(diff)

        assert result["added"] == ["new.py"]
        assert result["modified"] == ["modified.py"]
        assert result["deleted"] == ["deleted.py"]
        assert result["renamed"] == ["renamed.py"]

    def test_ignores_empty_lines(self):
        """Test ignoring empty lines."""
        diff = "A\tfile.py\n\nM\tanother.py\n"
        result = _parse_file_changes(diff)

        assert result["added"] == ["file.py"]
        assert result["modified"] == ["another.py"]

    def test_handles_empty_input(self):
        """Test handling empty input."""
        result = _parse_file_changes("")

        assert result["added"] == []
        assert result["modified"] == []
        assert result["deleted"] == []
        assert result["renamed"] == []

    def test_handles_malformed_lines(self):
        """Test handling malformed lines."""
        diff = "A\tfile.py\nmalformed_line\nM\tanother.py"
        result = _parse_file_changes(diff)

        assert result["added"] == ["file.py"]
        assert result["modified"] == ["another.py"]


class TestGetTaskMetadata:
    """Tests for _get_task_metadata function."""

    @patch("village.github_integration.subprocess.run")
    def test_gets_metadata_from_beads(self, mock_run):
        """Test getting metadata from Beads."""
        mock_run.return_value = subprocess.CompletedProcess(
            ["bd", "show", "bd-a3f8"],
            returncode=0,
            stdout="title: Fix bug\npriority: high\nagent: build",
            stderr="",
        )

        result = _get_task_metadata("bd-a3f8")

        assert result["title"] == "Fix bug"
        assert result["priority"] == "high"
        assert result["agent"] == "build"

    @patch("village.github_integration.subprocess.run")
    def test_handles_beads_unavailable(self, mock_run):
        """Test handling unavailable Beads."""
        mock_run.side_effect = FileNotFoundError()

        result = _get_task_metadata("bd-a3f8")

        assert result == {}

    @patch("village.github_integration.subprocess.run")
    def test_handles_beads_failure(self, mock_run):
        """Test handling Beads command failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["bd", "show"])

        result = _get_task_metadata("bd-a3f8")

        assert result == {}

    @patch("village.github_integration.subprocess.run")
    def test_ignores_comments(self, mock_run):
        """Test ignoring comment lines."""
        mock_run.return_value = subprocess.CompletedProcess(
            ["bd", "show", "bd-a3f8"],
            returncode=0,
            stdout="# Comment\ntitle: Task",
            stderr="",
        )

        result = _get_task_metadata("bd-a3f8")

        assert result["title"] == "Task"
        assert "Comment" not in result


class TestGenerateSummary:
    """Tests for _generate_summary function."""

    def test_generates_summary_with_title_and_description(self):
        """Test summary with title and description."""
        metadata = {"title": "Fix bug", "description": "Critical fix"}
        result = _generate_summary("bd-a3f8", metadata)

        assert "Fix bug" in result
        assert "Critical fix" in result

    def test_generates_summary_with_title_only(self):
        """Test summary with title only."""
        metadata = {"title": "Fix bug"}
        result = _generate_summary("bd-a3f8", metadata)

        assert result == "Fix bug"

    def test_generates_default_summary_without_metadata(self):
        """Test default summary when no metadata."""
        metadata = {}
        result = _generate_summary("bd-a3f8", metadata)

        assert result == "Work on task bd-a3f8"


class TestGenerateChangesSummary:
    """Tests for _generate_changes_summary function."""

    def test_generates_summary_for_changes(self):
        """Test generating changes summary."""
        changes = {
            "added": ["new.py", "another.py"],
            "modified": ["changed.py"],
            "deleted": ["removed.py"],
        }
        result = _generate_changes_summary(changes)

        assert "**Added** (2)" in result
        assert "**Modified** (1)" in result
        assert "**Deleted** (1)" in result
        assert "new.py" in result
        assert "changed.py" in result

    def test_handles_many_files(self):
        """Test handling many files in a category."""
        changes = {"added": [f"file_{i}.py" for i in range(15)]}
        result = _generate_changes_summary(changes)

        assert "file_0.py" in result
        assert "and 5 more" in result

    def test_handles_empty_changes(self):
        """Test handling empty changes."""
        changes = {"added": [], "modified": [], "deleted": [], "renamed": []}
        result = _generate_changes_summary(changes)

        assert result == "No changes detected"


class TestGenerateTestingChecklist:
    """Tests for _generate_testing_checklist function."""

    def test_generates_checklist_for_code_changes(self):
        """Test checklist for code changes."""
        changes = {"added": ["new.py"], "modified": ["changed.py"]}
        result = _generate_testing_checklist(changes)

        assert "- [ ] Code review completed" in result
        assert "- [ ] Unit tests passing" in result
        assert "- [ ] Integration tests passing" in result

    def test_includes_type_check_for_python(self):
        """Test including type check for Python files."""
        changes = {"added": ["script.py"], "modified": ["module.py"]}
        result = _generate_testing_checklist(changes)

        assert "- [ ] Type checking passed (mypy)" in result
        assert "- [ ] Linting passed (ruff)" in result

    def test_includes_test_coverage_for_test_files(self):
        """Test including test coverage check."""
        changes = {"added": ["test_script.py"], "modified": ["test_module.py"]}
        result = _generate_testing_checklist(changes)

        assert "- [ ] Test coverage reviewed" in result

    def test_includes_verification_for_deletions(self):
        """Test including verification for deletions."""
        changes = {"deleted": ["old.py"]}
        result = _generate_testing_checklist(changes)

        assert "- [ ] Verified no breaking changes from deletions" in result

    def test_handles_empty_changes(self):
        """Test handling empty changes."""
        changes = {"added": [], "modified": [], "deleted": []}
        result = _generate_testing_checklist(changes)

        assert result == []


class TestGenerateCommitSuggestions:
    """Tests for _generate_commit_suggestions function."""

    def test_generates_suggestions_from_metadata(self):
        """Test generating suggestions from metadata."""
        metadata = {"title": "Fix bug", "id": "bd-a3f8"}
        result = _generate_commit_suggestions(metadata)

        assert "feat: Fix bug" in result
        assert "chore: work on bd-a3f8" in result

    def test_handles_empty_metadata(self):
        """Test handling empty metadata."""
        metadata = {}
        result = _generate_commit_suggestions(metadata)

        assert result == []


class TestGeneratePRDescription:
    """Tests for generate_pr_description function."""

    @patch("village.github_integration._get_task_metadata")
    @patch("village.github_integration._get_git_diff")
    def test_generates_complete_description(self, mock_diff, mock_metadata, mock_worktree_path):
        """Test generating complete PR description."""
        mock_diff.return_value = "A\tnew.py\nM\tchanged.py"
        mock_metadata.return_value = {"title": "Feature", "description": "New feature"}

        result = generate_pr_description("bd-a3f8", mock_worktree_path)

        assert isinstance(result, PRDescription)
        assert "Feature" in result.summary
        assert "New feature" in result.summary
        assert result.changes
        assert len(result.testing_checklist) > 0
        assert "bd-a3f8" in result.related_tasks

    @patch("village.github_integration._get_task_metadata")
    @patch("village.github_integration._get_git_diff")
    def test_handles_git_failure(self, mock_diff, mock_metadata, mock_worktree_path):
        """Test handling git diff failure."""
        mock_diff.side_effect = GitHubError("git diff failed")

        with pytest.raises(GitHubError, match="git diff failed"):
            generate_pr_description("bd-a3f8", mock_worktree_path)


class TestSyncPRStatus:
    """Tests for sync_pr_status function."""

    @patch("village.github_integration._run_gh_command")
    def test_syncs_merged_pr(self, mock_run):
        """Test syncing merged PR status."""
        mock_run.return_value = json.dumps({"state": "closed", "merged": True})

        result = sync_pr_status("bd-a3f8", 123)

        assert result.success is True
        assert result.pr_number == 123
        assert result.pr_status == "merged"
        assert "merged" in result.message.lower()

    @patch("village.github_integration._run_gh_command")
    def test_syncs_open_pr(self, mock_run):
        """Test syncing open PR status."""
        mock_run.return_value = json.dumps({"state": "open", "merged": False})

        result = sync_pr_status("bd-a3f8", 123)

        assert result.success is True
        assert result.pr_status == "open"
        assert "open" in result.message.lower()

    @patch("village.github_integration._run_gh_command")
    def test_syncs_closed_pr(self, mock_run):
        """Test syncing closed PR status."""
        mock_run.return_value = json.dumps({"state": "closed", "merged": False})

        result = sync_pr_status("bd-a3f8", 123)

        assert result.success is True
        assert result.pr_status == "closed"
        assert "closed" in result.message.lower()

    @patch("village.github_integration._run_gh_command")
    def test_handles_gh_failure(self, mock_run):
        """Test handling gh command failure."""
        mock_run.side_effect = GitHubError("PR not found")

        result = sync_pr_status("bd-a3f8", 123)

        assert result.success is False
        assert result.pr_status == "error"
        assert "PR not found" in result.message

    @patch("village.github_integration._run_gh_command")
    def test_handles_json_parse_error(self, mock_run):
        """Test handling JSON parse error."""
        mock_run.return_value = "invalid json"

        result = sync_pr_status("bd-a3f8", 123)

        assert result.success is False
        assert result.pr_status == "error"
        assert "parse" in result.message.lower()


class TestAddPRLabels:
    """Tests for add_pr_labels function."""

    @patch("village.github_integration._run_gh_command")
    def test_adds_labels_to_pr(self, mock_run):
        """Test adding labels to PR."""
        add_pr_labels(123, ["bugfix", "enhancement"])

        mock_run.assert_called_once_with(["pr", "edit", "123", "--add-label", "bugfix,enhancement"])

    @patch("village.github_integration._run_gh_command")
    def test_skips_empty_labels(self, mock_run):
        """Test skipping when no labels provided."""
        add_pr_labels(123, [])

        mock_run.assert_not_called()

    @patch("village.github_integration._run_gh_command")
    def test_handles_single_label(self, mock_run):
        """Test adding single label."""
        add_pr_labels(123, ["bugfix"])

        mock_run.assert_called_once_with(["pr", "edit", "123", "--add-label", "bugfix"])

    @patch("village.github_integration._run_gh_command")
    def test_raises_on_failure(self, mock_run):
        """Test raising exception on failure."""
        mock_run.side_effect = GitHubError("Failed to add labels")

        with pytest.raises(GitHubError, match="Failed to add labels.*PR #123"):
            add_pr_labels(123, ["bugfix"])


class TestCreatePR:
    """Tests for create_pr function."""

    @patch("village.github_integration.add_pr_labels")
    @patch("village.github_integration._run_gh_command")
    def test_creates_pr_successfully(self, mock_run, mock_add_labels):
        """Test creating PR successfully."""
        mock_run.return_value = "https://github.com/user/repo/pull/123"
        description = PRDescription(
            summary="Feature implementation",
            changes="**Added** (1)\n  - new.py",
            testing_checklist=["- [ ] Tests pass"],
            related_tasks=["bd-a3f8"],
        )

        pr_number = create_pr("Feature", description, "feature-branch")

        assert pr_number == 123
        mock_run.assert_called_once()
        mock_add_labels.assert_not_called()

    @patch("village.github_integration.add_pr_labels")
    @patch("village.github_integration._run_gh_command")
    def test_creates_pr_with_labels(self, mock_run, mock_add_labels):
        """Test creating PR with labels."""
        mock_run.return_value = "https://github.com/user/repo/pull/123"
        description = PRDescription(summary="Feature", changes="No changes")

        pr_number = create_pr("Feature", description, "feature-branch", labels=["bugfix"])

        assert pr_number == 123
        mock_add_labels.assert_called_once_with(123, ["bugfix"])

    @patch("village.github_integration._run_gh_command")
    def test_creates_pr_with_custom_base(self, mock_run):
        """Test creating PR with custom base branch."""
        mock_run.return_value = "https://github.com/user/repo/pull/123"
        description = PRDescription(summary="Feature", changes="No changes")

        pr_number = create_pr("Feature", description, "feature-branch", base="develop")

        assert pr_number == 123
        call_args = mock_run.call_args[0][0]
        assert "--base" in call_args
        assert "develop" in call_args

    @patch("village.github_integration._run_gh_command")
    def test_raises_on_failure(self, mock_run):
        """Test raising exception on failure."""
        mock_run.side_effect = GitHubError("Failed to create PR")
        description = PRDescription(summary="Feature", changes="No changes")

        with pytest.raises(GitHubError, match="Failed to create PR"):
            create_pr("Feature", description, "feature-branch")


class TestPRDescription:
    """Tests for PRDescription dataclass."""

    def test_creates_description(self):
        """Test creating PRDescription."""
        desc = PRDescription(
            summary="Feature",
            changes="Changes",
            testing_checklist=["Test 1", "Test 2"],
            related_tasks=["bd-a3f8"],
            commit_suggestions=["feat: task"],
        )

        assert desc.summary == "Feature"
        assert desc.changes == "Changes"
        assert len(desc.testing_checklist) == 2
        assert len(desc.related_tasks) == 1
        assert len(desc.commit_suggestions) == 1

    def test_creates_minimal_description(self):
        """Test creating minimal PRDescription."""
        desc = PRDescription(summary="Feature", changes="Changes")

        assert desc.summary == "Feature"
        assert desc.testing_checklist == []
        assert desc.related_tasks == []
        assert desc.commit_suggestions == []


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_creates_successful_result(self):
        """Test creating successful SyncResult."""
        result = SyncResult(success=True, pr_number=123, pr_status="merged", message="PR merged")

        assert result.success is True
        assert result.pr_number == 123
        assert result.pr_status == "merged"
        assert result.message == "PR merged"

    def test_creates_failed_result(self):
        """Test creating failed SyncResult."""
        result = SyncResult(
            success=False, pr_number=123, pr_status="error", message="Error occurred"
        )

        assert result.success is False
        assert result.pr_status == "error"
        assert result.message == "Error occurred"


class TestGitHubError:
    """Tests for GitHubError exception."""

    def test_creates_error(self):
        """Test creating GitHubError."""
        error = GitHubError("Operation failed")

        assert str(error) == "Operation failed"
        assert isinstance(error, Exception)
