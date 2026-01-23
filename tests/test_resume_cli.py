"""Unit tests for village resume CLI command."""

from pathlib import Path
from unittest.mock import patch

import click.testing
import pytest

from village.cli import village
from village.config import Config
from village.resume import (
    ResumeAction,
    ResumeResult,
)


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


class TestResumeCLIBasic:
    """Basic command invocation tests."""

    def test_resume_no_args_uses_planner(self, runner, mock_config) -> None:
        """Test resume without args invokes planner."""
        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="ready",
            environment_ready=True,
            runtime_ready=True,
            work_available="none",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action:" in result.output

    def test_resume_with_task_id_executes_resume(self, runner, mock_config) -> None:
        """Test resume with task_id invokes execution."""
        result_obj = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="worker",
            worktree_path=mock_config.worktrees_dir / "bd-a3f8",
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj):
            with patch("village.resume.plan_resume"):
                result = runner.invoke(village, ["resume", "bd-a3f8"])

                assert result.exit_code == 0
                assert "✓ Resume successful" in result.output

    def test_resume_help_displays_help(self, runner) -> None:
        """Test resume --help displays help."""
        result = runner.invoke(village, ["resume", "--help"])

        assert result.exit_code == 0
        assert "Resume a task" in result.output


class TestResumeCLIEquivalenceClasses:
    """Flag equivalence class tests using parametrize."""

    @pytest.mark.parametrize(
        "agent,detached,html,dry_run,task_id",
        [
            # Baseline: no flags, with task_id
            (None, False, False, False, "bd-a3f8"),
            # Single flags
            ("build", False, False, False, "bd-a3f8"),  # --agent
            (None, True, False, False, "bd-a3f8"),  # --detached
            (None, False, True, False, "bd-a3f8"),  # --html
            (None, False, False, True, "bd-a3f8"),  # --dry-run
            # Planner mode (no task_id)
            (None, False, False, False, None),
        ],
    )
    def test_resume_flag_equivalence(self, runner, agent, detached, html, dry_run, task_id) -> None:
        """Test flag behavior by equivalence class."""
        result_obj = ResumeResult(
            success=True,
            task_id=task_id or "bd-a3f8",
            agent=agent or "worker",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj):
            with patch("village.resume.plan_resume"):
                args = ["resume"]
                if task_id:
                    args.append(task_id)
                if agent:
                    args.extend(["--agent", agent])
                if detached:
                    args.append("--detached")
                if html:
                    args.append("--html")
                if dry_run:
                    args.append("--dry-run")

                result = runner.invoke(village, args)

                assert result.exit_code == 0


class TestResumeCLIPlanner:
    """Planner mode tests (no task_id)."""

    def test_planner_suggests_up(self, runner) -> None:
        """Test planner suggests 'village up' when not initialized."""
        action = ResumeAction(
            action="up",
            reason="Village runtime not initialized",
            blocking=True,
            meta={"command": "village up"},
        )

        with patch("village.resume.plan_resume", return_value=action):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action: village up" in result.output

    def test_planner_suggests_cleanup(self, runner) -> None:
        """Test planner suggests 'village cleanup' with stale locks."""
        action = ResumeAction(
            action="cleanup",
            reason="3 stale lock(s) found",
            blocking=False,
            meta={"command": "village cleanup"},
        )

        with patch("village.resume.plan_resume", return_value=action):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action: village cleanup" in result.output

    def test_planner_suggests_status(self, runner) -> None:
        """Test planner suggests 'village status' with active task."""
        action = ResumeAction(
            action="status",
            reason="Task bd-a3f8 already has ACTIVE lock",
            blocking=False,
            meta={"command": "village status --workers"},
        )

        with patch("village.resume.plan_resume", return_value=action):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action: village status" in result.output

    def test_planner_suggests_queue(self, runner) -> None:
        """Test planner suggests 'village queue' with ready tasks."""
        action = ResumeAction(
            action="queue",
            reason="3 ready task(s) available",
            blocking=False,
            meta={"command": "village queue"},
        )

        with patch("village.resume.plan_resume", return_value=action):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action: village queue" in result.output

    def test_planner_suggests_ready(self, runner) -> None:
        """Test planner suggests 'village ready' with no tasks."""
        action = ResumeAction(
            action="ready",
            reason="No specific task ID provided",
            blocking=False,
            meta={"command": "village ready"},
        )

        with patch("village.resume.plan_resume", return_value=action):
            result = runner.invoke(village, ["resume"])

            assert result.exit_code == 0
            assert "Action: village ready" in result.output


class TestResumeCLIAgentSelection:
    """Agent selection tests."""

    def test_agent_explicit(self, runner, mock_config) -> None:
        """Test --agent flag uses specified agent."""
        result_obj = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="build",
            worktree_path=mock_config.worktrees_dir / "bd-a3f8",
            window_name="build-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj) as mock_exec:
            result = runner.invoke(village, ["resume", "bd-a3f8", "--agent", "build"])

            assert result.exit_code == 0
            # Verify agent passed to execute_resume
            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["agent"] == "build"

    def test_agent_default(self, runner, mock_config) -> None:
        """Test no --agent uses config.default_agent."""
        result_obj = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="worker",
            worktree_path=mock_config.worktrees_dir / "bd-a3f8",
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        with patch("village.cli.execute_resume", return_value=result_obj) as mock_exec:
            result = runner.invoke(village, ["resume", "bd-a3f8"])

            assert result.exit_code == 0
            # Verify default_agent used
            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["agent"] == "worker"
