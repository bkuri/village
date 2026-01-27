"""Test conflict detection module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from village.config import Config
from village.conflict_detection import (
    Conflict,
    ConflictReport,
    WorkerInfo,
    _detect_vcs,
    _get_git_modified_files,
    _get_jj_modified_files,
    detect_file_conflicts,
    find_overlaps,
    get_modified_files,
    render_conflict_report,
    render_conflict_report_json,
)
from village.probes.tools import SubprocessError


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    return config


class TestWorkerInfo:
    """Tests for WorkerInfo dataclass."""

    def test_worker_info_creation(self):
        """Test creating a WorkerInfo."""
        worker = WorkerInfo(
            task_id="bd-a3f8",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            pane_id="%12",
            window_id="build-1-bd-a3f8",
        )
        assert worker.task_id == "bd-a3f8"
        assert worker.worktree_path == Path("/tmp/.worktrees/bd-a3f8")
        assert worker.pane_id == "%12"
        assert worker.window_id == "build-1-bd-a3f8"


class TestConflict:
    """Tests for Conflict dataclass."""

    def test_conflict_creation(self):
        """Test creating a Conflict."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8", "bd-b7d2"],
            worktrees=[Path("/tmp/.worktrees/bd-a3f8"), Path("/tmp/.worktrees/bd-b7d2")],
        )
        assert conflict.file == Path("/repo/src/main.py")
        assert conflict.workers == ["bd-a3f8", "bd-b7d2"]
        assert len(conflict.worktrees) == 2


class TestConflictReport:
    """Tests for ConflictReport dataclass."""

    def test_conflict_report_no_conflicts(self):
        """Test creating ConflictReport with no conflicts."""
        report = ConflictReport(has_conflicts=False, conflicts=[], blocked=False)
        assert report.has_conflicts is False
        assert len(report.conflicts) == 0
        assert report.blocked is False

    def test_conflict_report_with_conflicts(self):
        """Test creating ConflictReport with conflicts."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8", "bd-b7d2"],
            worktrees=[],
        )
        report = ConflictReport(has_conflicts=True, conflicts=[conflict], blocked=True)
        assert report.has_conflicts is True
        assert len(report.conflicts) == 1
        assert report.blocked is True


class TestDetectVcs:
    """Tests for _detect_vcs function."""

    def test_detect_git_vcs(self, tmp_path: Path):
        """Test detecting git repository."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".git").mkdir()

        vcs = _detect_vcs(worktree_path)
        assert vcs == "git"

    def test_detect_jj_vcs(self, tmp_path: Path):
        """Test detecting jj repository."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".jj").mkdir()

        vcs = _detect_vcs(worktree_path)
        assert vcs == "jj"

    def test_detect_no_vcs(self, tmp_path: Path):
        """Test detecting no VCS."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        vcs = _detect_vcs(worktree_path)
        assert vcs is None


class TestGetGitModifiedFiles:
    """Tests for _get_git_modified_files function."""

    def test_git_modified_files_single(self, tmp_path: Path):
        """Test getting single modified file from git."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = "M src/main.py"

            files = _get_git_modified_files(worktree_path)

            assert len(files) == 1
            assert files[0] == worktree_path / "src/main.py"

    def test_git_modified_files_multiple(self, tmp_path: Path):
        """Test getting multiple modified files from git."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        output = """M src/main.py
M src/utils.py
A tests/test_main.py"""
        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = output

            files = _get_git_modified_files(worktree_path)

            assert len(files) == 3
            assert files[0] == worktree_path / "src/main.py"
            assert files[1] == worktree_path / "src/utils.py"
            assert files[2] == worktree_path / "tests/test_main.py"

    def test_git_modified_files_absolute_path(self, tmp_path: Path):
        """Test handling absolute paths in git status."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        absolute_file = tmp_path / "absolute.py"
        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = f"M {absolute_file}"

            files = _get_git_modified_files(worktree_path)

            assert len(files) == 1
            assert files[0] == absolute_file

    def test_git_modified_files_empty(self, tmp_path: Path):
        """Test handling empty git status."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = ""

            files = _get_git_modified_files(worktree_path)

            assert len(files) == 0

    def test_git_modified_files_subprocess_error(self, tmp_path: Path):
        """Test handling subprocess error in git."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.side_effect = SubprocessError("git failed")

            with pytest.raises(SubprocessError):
                _get_git_modified_files(worktree_path)


class TestGetJJModifiedFiles:
    """Tests for _get_jj_modified_files function."""

    def test_jj_modified_files_single(self, tmp_path: Path):
        """Test getting single modified file from jj."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = "src/main.py"

            files = _get_jj_modified_files(worktree_path)

            assert len(files) == 1
            assert files[0] == worktree_path / "src/main.py"

    def test_jj_modified_files_multiple(self, tmp_path: Path):
        """Test getting multiple modified files from jj."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        output = """src/main.py
src/utils.py
tests/test_main.py"""
        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = output

            files = _get_jj_modified_files(worktree_path)

            assert len(files) == 3
            assert files[0] == worktree_path / "src/main.py"
            assert files[1] == worktree_path / "src/utils.py"
            assert files[2] == worktree_path / "tests/test_main.py"

    def test_jj_modified_files_empty(self, tmp_path: Path):
        """Test handling empty jj diff."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with patch("village.conflict_detection.run_command_output_cwd") as mock_run:
            mock_run.return_value = ""

            files = _get_jj_modified_files(worktree_path)

            assert len(files) == 0


class TestGetModifiedFiles:
    """Tests for get_modified_files function."""

    def test_get_modified_files_git(self, tmp_path: Path):
        """Test get_modified_files with git."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".git").mkdir()

        with patch("village.conflict_detection._get_git_modified_files") as mock_git:
            mock_git.return_value = [worktree_path / "src/main.py"]

            files = get_modified_files(worktree_path)

            assert len(files) == 1
            mock_git.assert_called_once()

    def test_get_modified_files_jj(self, tmp_path: Path):
        """Test get_modified_files with jj."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        (worktree_path / ".jj").mkdir()

        with patch("village.conflict_detection._get_jj_modified_files") as mock_jj:
            mock_jj.return_value = [worktree_path / "src/main.py"]

            files = get_modified_files(worktree_path)

            assert len(files) == 1
            mock_jj.assert_called_once()

    def test_get_modified_files_no_vcs(self, tmp_path: Path):
        """Test get_modified_files with no VCS."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        files = get_modified_files(worktree_path)

        assert len(files) == 0

    def test_get_modified_files_not_exists(self, tmp_path: Path):
        """Test get_modified_files with non-existent worktree."""
        worktree_path = tmp_path / "nonexistent"

        with pytest.raises(RuntimeError, match="does not exist"):
            get_modified_files(worktree_path)


class TestFindOverlaps:
    """Tests for find_overlaps function."""

    def test_find_overlaps_no_conflicts(self):
        """Test finding overlaps with no conflicts."""
        all_files = {
            "bd-a3f8": [Path("/repo/src/a.py")],
            "bd-b7d2": [Path("/repo/src/b.py")],
        }

        conflicts = find_overlaps(all_files)

        assert len(conflicts) == 0

    def test_find_overlaps_single_conflict(self):
        """Test finding single file conflict."""
        file_path = Path("/repo/src/main.py")
        all_files = {
            "bd-a3f8": [file_path],
            "bd-b7d2": [file_path],
        }

        conflicts = find_overlaps(all_files)

        assert len(conflicts) == 1
        assert conflicts[0].file == file_path
        assert set(conflicts[0].workers) == {"bd-a3f8", "bd-b7d2"}

    def test_find_overlaps_multiple_conflicts(self):
        """Test finding multiple file conflicts."""
        file1 = Path("/repo/src/main.py")
        file2 = Path("/repo/src/utils.py")

        all_files = {
            "bd-a3f8": [file1, file2],
            "bd-b7d2": [file1, file2],
            "bd-c4e1": [Path("/repo/src/other.py")],
        }

        conflicts = find_overlaps(all_files)

        assert len(conflicts) == 2

        conflict_files = {c.file for c in conflicts}
        assert file1 in conflict_files
        assert file2 in conflict_files

    def test_find_overlaps_three_way_conflict(self):
        """Test finding three-way conflict."""
        file_path = Path("/repo/src/main.py")

        all_files = {
            "bd-a3f8": [file_path],
            "bd-b7d2": [file_path],
            "bd-c4e1": [file_path],
        }

        conflicts = find_overlaps(all_files)

        assert len(conflicts) == 1
        assert len(conflicts[0].workers) == 3
        assert set(conflicts[0].workers) == {"bd-a3f8", "bd-b7d2", "bd-c4e1"}

    def test_find_overlaps_empty_dict(self):
        """Test finding overlaps with empty input."""
        conflicts = find_overlaps({})
        assert len(conflicts) == 0

    def test_find_overlaps_mixed_modified_files(self):
        """Test finding overlaps with mixed modified files."""
        shared_file = Path("/repo/src/main.py")
        unique_a = Path("/repo/src/a.py")
        unique_b = Path("/repo/src/b.py")

        all_files = {
            "bd-a3f8": [shared_file, unique_a],
            "bd-b7d2": [shared_file, unique_b],
        }

        conflicts = find_overlaps(all_files)

        assert len(conflicts) == 1
        assert conflicts[0].file == shared_file


class TestDetectFileConflicts:
    """Tests for detect_file_conflicts function."""

    def test_detect_no_conflicts(self, mock_config: Config, tmp_path: Path):
        """Test detecting no conflicts."""
        worktree_a = tmp_path / "bd-a3f8"
        worktree_a.mkdir()
        (worktree_a / ".git").mkdir()

        worktree_b = tmp_path / "bd-b7d2"
        worktree_b.mkdir()
        (worktree_b / ".git").mkdir()

        workers = [
            WorkerInfo(
                task_id="bd-a3f8",
                worktree_path=worktree_a,
                pane_id="%12",
                window_id="build-1-bd-a3f8",
            ),
            WorkerInfo(
                task_id="bd-b7d2",
                worktree_path=worktree_b,
                pane_id="%13",
                window_id="test-1-bd-b7d2",
            ),
        ]

        with patch("village.conflict_detection._get_git_modified_files") as mock_git:
            mock_git.side_effect = lambda p: [p / f"{p.name}.py"]

            report = detect_file_conflicts(workers, mock_config)

            assert report.has_conflicts is False
            assert len(report.conflicts) == 0
            assert report.blocked is False

    def test_detect_with_conflicts_not_blocked(self, mock_config: Config, tmp_path: Path):
        """Test detecting conflicts when not blocked."""
        worktree_a = tmp_path / "bd-a3f8"
        worktree_a.mkdir()
        (worktree_a / ".git").mkdir()

        worktree_b = tmp_path / "bd-b7d2"
        worktree_b.mkdir()
        (worktree_b / ".git").mkdir()

        workers = [
            WorkerInfo(
                task_id="bd-a3f8",
                worktree_path=worktree_a,
                pane_id="%12",
                window_id="build-1-bd-a3f8",
            ),
            WorkerInfo(
                task_id="bd-b7d2",
                worktree_path=worktree_b,
                pane_id="%13",
                window_id="test-1-bd-b7d2",
            ),
        ]

        shared_file = tmp_path / "shared.py"
        with patch("village.conflict_detection._get_git_modified_files") as mock_git:
            mock_git.side_effect = lambda p: [shared_file]

            report = detect_file_conflicts(workers, mock_config)

            assert report.has_conflicts is True
            assert len(report.conflicts) == 1
            assert report.blocked is False

    def test_detect_with_conflicts_blocked(self, mock_config: Config, tmp_path: Path):
        """Test detecting conflicts when blocked."""
        worktree_a = tmp_path / "bd-a3f8"
        worktree_a.mkdir()
        (worktree_a / ".git").mkdir()

        worktree_b = tmp_path / "bd-b7d2"
        worktree_b.mkdir()
        (worktree_b / ".git").mkdir()

        workers = [
            WorkerInfo(
                task_id="bd-a3f8",
                worktree_path=worktree_a,
                pane_id="%12",
                window_id="build-1-bd-a3f8",
            ),
            WorkerInfo(
                task_id="bd-b7d2",
                worktree_path=worktree_b,
                pane_id="%13",
                window_id="test-1-bd-b7d2",
            ),
        ]

        shared_file = tmp_path / "shared.py"
        with patch("village.conflict_detection._get_git_modified_files") as mock_git:
            mock_git.side_effect = lambda p: [shared_file]

            mock_config.conflict.block_on_conflict = True
            report = detect_file_conflicts(workers, mock_config)

            assert report.has_conflicts is True
            assert len(report.conflicts) == 1
            assert report.blocked is True

    def test_detect_uses_default_config(self, tmp_path: Path):
        """Test that default config is used when not provided."""
        worktree_a = tmp_path / "bd-a3f8"
        worktree_a.mkdir()
        (worktree_a / ".git").mkdir()

        workers = [
            WorkerInfo(
                task_id="bd-a3f8",
                worktree_path=worktree_a,
                pane_id="%12",
                window_id="build-1-bd-a3f8",
            ),
        ]

        with patch("village.conflict_detection.get_config") as mock_get_config:
            mock_config = Config(
                git_root=tmp_path,
                village_dir=tmp_path / ".village",
                worktrees_dir=tmp_path / ".worktrees",
            )
            mock_get_config.return_value = mock_config

            with patch("village.conflict_detection._get_git_modified_files") as mock_git:
                mock_git.return_value = []

                detect_file_conflicts(workers)

                mock_get_config.assert_called_once()

    def test_detect_handles_worker_errors(self, mock_config: Config, tmp_path: Path):
        """Test detecting conflicts handles worker errors gracefully."""
        worktree_a = tmp_path / "bd-a3f8"
        worktree_a.mkdir()
        (worktree_a / ".git").mkdir()

        worktree_b = tmp_path / "bd-b7d2"

        workers = [
            WorkerInfo(
                task_id="bd-a3f8",
                worktree_path=worktree_a,
                pane_id="%12",
                window_id="build-1-bd-a3f8",
            ),
            WorkerInfo(
                task_id="bd-b7d2",
                worktree_path=worktree_b,
                pane_id="%13",
                window_id="test-1-bd-b7d2",
            ),
        ]

        with patch("village.conflict_detection._get_git_modified_files") as mock_git:
            mock_git.return_value = []

            report = detect_file_conflicts(workers, mock_config)

            assert report.has_conflicts is False
            assert len(report.conflicts) == 0


class TestRenderConflictReport:
    """Tests for render_conflict_report function."""

    def test_render_no_conflicts(self):
        """Test rendering report with no conflicts."""
        report = ConflictReport(has_conflicts=False, conflicts=[], blocked=False)

        output = render_conflict_report(report)

        assert "No file conflicts detected" in output

    def test_render_with_conflicts(self):
        """Test rendering report with conflicts."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8", "bd-b7d2"],
            worktrees=[],
        )
        report = ConflictReport(has_conflicts=True, conflicts=[conflict], blocked=False)

        output = render_conflict_report(report)

        assert "File conflicts detected: 1" in output
        assert "/repo/src/main.py" in output
        assert "bd-a3f8" in output
        assert "bd-b7d2" in output
        assert "Proceeding with conflicts" in output

    def test_render_blocked(self):
        """Test rendering report when blocked."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8", "bd-b7d2"],
            worktrees=[],
        )
        report = ConflictReport(has_conflicts=True, conflicts=[conflict], blocked=True)

        output = render_conflict_report(report)

        assert "Execution blocked due to conflicts" in output
        assert "BLOCK_ON_CONFLICT=True" in output

    def test_render_multiple_conflicts(self):
        """Test rendering report with multiple conflicts."""
        conflicts = [
            Conflict(
                file=Path("/repo/src/a.py"),
                workers=["bd-a3f8", "bd-b7d2"],
                worktrees=[],
            ),
            Conflict(
                file=Path("/repo/src/b.py"),
                workers=["bd-a3f8", "bd-c4e1"],
                worktrees=[],
            ),
        ]
        report = ConflictReport(has_conflicts=True, conflicts=conflicts, blocked=False)

        output = render_conflict_report(report)

        assert "File conflicts detected: 2" in output
        assert "/repo/src/a.py" in output
        assert "/repo/src/b.py" in output


class TestRenderConflictReportJson:
    """Tests for render_conflict_report_json function."""

    def test_render_json_no_conflicts(self):
        """Test JSON rendering with no conflicts."""
        report = ConflictReport(has_conflicts=False, conflicts=[], blocked=False)

        json_output = render_conflict_report_json(report)
        data = json.loads(json_output)

        assert data["has_conflicts"] is False
        assert data["conflicts"] == []
        assert data["blocked"] is False

    def test_render_json_with_conflicts(self):
        """Test JSON rendering with conflicts."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8", "bd-b7d2"],
            worktrees=[Path("/tmp/w1"), Path("/tmp/w2")],
        )
        report = ConflictReport(has_conflicts=True, conflicts=[conflict], blocked=True)

        json_output = render_conflict_report_json(report)
        data = json.loads(json_output)

        assert data["has_conflicts"] is True
        assert data["blocked"] is True
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["file"] == "/repo/src/main.py"
        assert data["conflicts"][0]["workers"] == ["bd-a3f8", "bd-b7d2"]
        assert data["conflicts"][0]["worktrees"] == ["/tmp/w1", "/tmp/w2"]

    def test_render_json_valid(self):
        """Test JSON output is valid."""
        conflict = Conflict(
            file=Path("/repo/src/main.py"),
            workers=["bd-a3f8"],
            worktrees=[],
        )
        report = ConflictReport(has_conflicts=True, conflicts=[conflict], blocked=False)

        json_output = render_conflict_report_json(report)

        json.loads(json_output)
        assert json_output is not None

    def test_render_json_sorted_keys(self):
        """Test JSON keys are sorted."""
        report = ConflictReport(has_conflicts=False, conflicts=[], blocked=False)

        json_output = render_conflict_report_json(report)
        data = json.loads(json_output)

        keys = list(data.keys())
        assert keys == sorted(keys)
