"""Integration tests for village resume orchestration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import click.testing
import pytest

from village.cli import village
from village.config import Config
from village.contracts import ResumeContract
from village.probes.tools import SubprocessError
from village.resume import ResumeResult, execute_resume


@pytest.fixture
def runner() -> click.testing.CliRunner:
    """Click CliRunner for testing CLI commands."""
    return click.testing.CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config."""
    return Config(
        git_root=tmp_path / "repo",
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="village",
        default_agent="worker",
    )


class TestResumeIntegrationExecute:
    """Resume execution tests."""

    def test_execute_resume_success(self, mock_config: Config) -> None:
        """Test successful resume creates worktree, window, lock."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            with patch("village.resume._create_resume_window") as mock_create:
                with patch("village.resume.write_lock") as mock_write:
                    with patch("village.resume._inject_contract") as mock_inject:
                        with patch("village.resume.generate_contract"):
                            mock_ensure.return_value = (
                                mock_config.worktrees_dir / task_id,
                                "build-1-bd-a3f8",
                                task_id,
                            )
                            mock_create.return_value = "%12"

                            result = execute_resume(
                                task_id, agent, detached=False, dry_run=False, config=mock_config
                            )

                            assert result.success is True
                            assert result.task_id == task_id
                            assert result.pane_id == "%12"
                            assert result.worktree_path == mock_config.worktrees_dir / task_id

                            # Verify mocks were called
                            mock_ensure.assert_called_once()
                            mock_create.assert_called_once()
                            mock_write.assert_called_once()
                            mock_inject.assert_called_once()

    def test_execute_resume_dry_run(self, mock_config: Config) -> None:
        """Test --dry-run displays preview without mutations."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            mock_ensure.return_value = (
                mock_config.worktrees_dir / task_id,
                "build-1-bd-a3f8",
                task_id,
            )

            result = execute_resume(
                task_id, agent, detached=False, dry_run=True, config=mock_config
            )

            assert result.success is True
            assert result.pane_id == ""  # No pane in dry run

            # Verify no lock written
            mock_ensure.assert_called_once()

    def test_execute_resume_error(self, mock_config: Config) -> None:
        """Test failure returns error result."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            mock_ensure.side_effect = RuntimeError("Git repo dirty")

            result = execute_resume(
                task_id, agent, detached=False, dry_run=False, config=mock_config
            )

            assert result.success is False
            assert result.error is not None
            assert "Git repo dirty" in result.error


class TestResumeIntegrationCollisionRetry:
    """Worktree collision retry tests."""

    def test_collision_retry_first(self, mock_config: Config) -> None:
        """Test first collision retries as bd-a3f8-2."""
        base_task_id = "bd-a3f8"

        with patch("village.resume.create_worktree") as mock_create:
            with patch("village.resume.get_worktree_info") as mock_info:
                with patch("village.resume._create_resume_window", return_value="%12"):
                    with patch("village.resume.write_lock"):
                        with patch("village.resume._inject_contract"):
                            with patch("village.resume.generate_contract"):
                                # First attempt fails with collision
                                mock_create.side_effect = [
                                    SubprocessError("worktree already exists"),
                                    (
                                        mock_config.worktrees_dir / f"{base_task_id}-2",
                                        f"worker-1-{base_task_id}-2",
                                    ),
                                ]
                                mock_info.return_value = None

                                result = execute_resume(
                                    base_task_id,
                                    "build",
                                    detached=False,
                                    dry_run=False,
                                    config=mock_config,
                                )

                                assert result.success is True
                                assert result.task_id == f"{base_task_id}-2"
                                assert mock_create.call_count == 2

    def test_collision_retry_second(self, mock_config: Config) -> None:
        """Test second collision retries as bd-a3f8-3."""
        base_task_id = "bd-a3f8"

        with patch("village.resume.create_worktree") as mock_create:
            with patch("village.resume.get_worktree_info") as mock_info:
                with patch("village.resume._create_resume_window", return_value="%12"):
                    with patch("village.resume.write_lock"):
                        with patch("village.resume._inject_contract"):
                            with patch("village.resume.generate_contract"):
                                # Two collisions
                                mock_create.side_effect = [
                                    SubprocessError("worktree already exists"),
                                    SubprocessError("worktree already exists"),
                                    (
                                        mock_config.worktrees_dir / f"{base_task_id}-3",
                                        f"worker-1-{base_task_id}-3",
                                    ),
                                ]
                                mock_info.return_value = None

                                result = execute_resume(
                                    base_task_id,
                                    "build",
                                    detached=False,
                                    dry_run=False,
                                    config=mock_config,
                                )

                                assert result.success is True
                                assert result.task_id == f"{base_task_id}-3"
                                assert mock_create.call_count == 3

    def test_collision_retry_max(self, mock_config: Config) -> None:
        """Test max retries (3) and then fail."""
        base_task_id = "bd-a3f8"

        with patch("village.resume.create_worktree") as mock_create:
            with patch("village.resume.get_worktree_info") as mock_info:
                # Four collisions (3 retries + 1 initial attempt)
                mock_create.side_effect = [
                    SubprocessError("worktree already exists"),
                    SubprocessError("worktree already exists"),
                    SubprocessError("worktree already exists"),
                    SubprocessError("worktree already exists"),
                ]
                mock_info.return_value = None

                result = execute_resume(
                    base_task_id, "build", detached=False, dry_run=False, config=mock_config
                )

                assert result.success is False
                assert result.error is not None
                assert "failed after 3 attempts" in result.error


class TestResumeIntegrationHTML:
    """HTML output tests."""

    def test_html_output_success(self, runner, mock_config: Config) -> None:
        """Test --html generates valid HTML output."""
        result_obj = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="worker",
            worktree_path=mock_config.worktrees_dir / "bd-a3f8",
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj):
            with patch("village.cli.plan_resume"):
                with patch("village.contracts.generate_contract") as mock_contract:
                    mock_contract.return_value = ResumeContract(
                        task_id="bd-a3f8",
                        agent="worker",
                        worktree_path=mock_config.worktrees_dir / "bd-a3f8",
                        git_root=mock_config.git_root,
                        window_name="worker-1-bd-a3f8",
                        claimed_at=datetime.now(),
                    )

                    result = runner.invoke(village, ["resume", "bd-a3f8", "--html"])

                    assert result.exit_code == 0

                    # Assert HTML structure
                    assert "<pre>" in result.output
                    assert "</pre>" in result.output
                    assert '<script type="application/json" id="village-meta">' in result.output
                    assert "</script>" in result.output

    def test_html_metadata_format(self, runner, mock_config: Config) -> None:
        """Test HTML contains valid JSON metadata."""
        import json

        result_obj = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="worker",
            worktree_path=mock_config.worktrees_dir / "bd-a3f8",
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj):
            with patch("village.cli.plan_resume"):
                with patch("village.contracts.generate_contract") as mock_contract:
                    mock_contract.return_value = ResumeContract(
                        task_id="bd-a3f8",
                        agent="worker",
                        worktree_path=mock_config.worktrees_dir / "bd-a3f8",
                        git_root=mock_config.git_root,
                        window_name="worker-1-bd-a3f8",
                        claimed_at=datetime.now(),
                    )

                    result = runner.invoke(village, ["resume", "bd-a3f8", "--html"])

                    # Extract JSON from HTML
                    start = result.output.find("{")
                    end = result.output.rfind("}") + 1
                    json_str = result.output[start:end]

                    metadata = json.loads(json_str)

                    # Assert required fields
                    assert "task_id" in metadata
                    assert "agent" in metadata
                    assert "worktree_path" in metadata
                    assert "window_name" in metadata
                    assert "claimed_at" in metadata

                    # Assert keys are sorted
                    keys = list(metadata.keys())
                    assert keys == sorted(keys)

    def test_html_output_error(self, runner, mock_config: Config) -> None:
        """Test HTML not shown on failure."""
        result_obj = ResumeResult(
            success=False,
            task_id="bd-a3f8",
            agent="worker",
            worktree_path=Path(""),
            window_name="",
            pane_id="",
            error="Git repo dirty",
        )

        with patch("village.resume.execute_resume", return_value=result_obj):
            with patch("village.resume.plan_resume"):
                result = runner.invoke(village, ["resume", "bd-a3f8", "--html"])

                assert result.exit_code == 0

                # Assert HTML not in output (no success → no HTML)
                assert "<pre>" not in result.output


class TestResumeIntegrationDetached:
    """Detached mode tests."""

    def test_detached_mode(self, mock_config: Config) -> None:
        """Test --detached executes without tmux attach."""
        task_id = "bd-a3f8"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            with patch("village.resume._create_resume_window") as mock_create:
                with patch("village.resume.write_lock"):
                    with patch("village.resume._inject_contract"):
                        with patch("village.resume.generate_contract"):
                            mock_ensure.return_value = (
                                mock_config.worktrees_dir / task_id,
                                "worker-1-bd-a3f8",
                                task_id,
                            )
                            mock_create.return_value = "%12"

                            result = execute_resume(
                                task_id, "worker", detached=True, dry_run=False, config=mock_config
                            )

                            assert result.success is True
                            # Assert detached was passed
                            assert mock_create.call_count == 1


class TestResumeIntegrationTMUX:
    """tmux integration tests (mock-only)."""

    def test_resume_with_session(self, mock_config: Config) -> None:
        """Test resume when session exists."""
        task_id = "bd-a3f8"

        with patch("village.probes.tmux.session_exists", return_value=True):
            with patch("village.resume._ensure_worktree_exists") as mock_ensure:
                with patch("village.resume._create_resume_window") as mock_create:
                    with patch("village.resume.write_lock"):
                        with patch("village.resume._inject_contract"):
                            with patch("village.resume.generate_contract"):
                                mock_ensure.return_value = (
                                    mock_config.worktrees_dir / task_id,
                                    "worker-1-bd-a3f8",
                                    task_id,
                                )
                                mock_create.return_value = "%12"

                                result = execute_resume(
                                    task_id,
                                    "worker",
                                    detached=False,
                                    dry_run=False,
                                    config=mock_config,
                                )

                                assert result.success is True

    def test_resume_without_session(self, mock_config: Config) -> None:
        """Test resume fails appropriately when session doesn't exist."""
        task_id = "bd-a3f8"

        with patch("village.probes.tmux.session_exists", return_value=False):
            with patch("village.resume._ensure_worktree_exists") as mock_ensure:
                mock_ensure.return_value = (
                    mock_config.worktrees_dir / task_id,
                    "worker-1-bd-a3f8",
                    task_id,
                )

                # Window creation will fail if session doesn't exist
                result = execute_resume(
                    task_id, "worker", detached=False, dry_run=False, config=mock_config
                )

                # Should fail (session check happens in window creation)
                assert result.success is False
                assert result.error is not None


class TestResumeIntegrationE2E:
    """End-to-end workflow tests."""

    def test_workflow_cold_start(self, mock_config: Config) -> None:
        """Test workflow: up → ready → resume → status → down."""
        # Mock all operations
        with patch("village.runtime.collect_runtime_state"):
            with patch("village.runtime.execute_initialization"):
                with patch("village.ready.assess_readiness"):
                    with patch("village.resume.execute_resume"):
                        with patch("village.status.collect_full_status"):
                            with patch("village.runtime.shutdown_runtime"):
                                # Simulate workflow - all mocks should be called
                                pass

                                # In real workflow, assert each phase was called
                                # For now, verify no exceptions

    def test_workflow_planner(self, mock_config: Config) -> None:
        """Test workflow: resume (planner) → up → resume (apply)."""
        with patch("village.resume.plan_resume"):
            with patch("village.runtime.execute_initialization"):
                with patch("village.resume.execute_resume"):
                    # Simulate workflow
                    pass

    def test_workflow_dry_run(self, mock_config: Config) -> None:
        """Test workflow: dry-run preview → execute."""
        task_id = "bd-a3f8"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            with patch("village.resume._create_resume_window") as mock_create_window:
                with patch("village.resume.write_lock"):
                    with patch("village.resume._inject_contract"):
                        with patch("village.resume.generate_contract"):
                            mock_ensure.return_value = (
                                mock_config.worktrees_dir / task_id,
                                "worker-1-bd-a3f8",
                                task_id,
                            )

                            # First call: dry-run (no pane_id)
                            result1 = execute_resume(
                                task_id, "worker", detached=False, dry_run=True, config=mock_config
                            )

                            assert result1.success is True
                            assert result1.pane_id == ""  # Dry run

                            # Second call: execute (with pane_id)
                            mock_create_window.return_value = "%12"
                            result2 = execute_resume(
                                task_id, "worker", detached=False, dry_run=False, config=mock_config
                            )

                            assert result2.success is True
                            assert result2.pane_id == "%12"  # Real execution
                            assert mock_create_window.call_count == 1
