"""Test queue CLI command."""

from pathlib import Path
from unittest.mock import patch

import click.testing
import pytest

from village.cli import village
from village.config import Config
from village.errors import EXIT_BLOCKED
from village.queue import QueuePlan, QueueTask


@pytest.fixture
def runner() -> click.testing.CliRunner:
    """Click CliRunner for testing CLI commands."""
    return click.testing.CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    return config


class TestQueueCLIPlan:
    """Plan mode tests (no task execution)."""

    def test_queue_plan_shows_summary(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test queue plan shows summary."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue"])

                assert result.exit_code == 0
                assert "Ready tasks: 2" in result.output
                assert "Available tasks: 2" in result.output
                assert "Slots available: 2" in result.output

    def test_queue_plan_json_output(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test queue plan JSON output."""
        import json

        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test", skip_reason="active_lock"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks[:1],
            blocked_tasks=tasks[1:],
            slots_available=1,
            workers_count=1,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue", "--plan", "--json"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["ready_tasks"][0]["task_id"] == "bd-a3f8"
                assert data["blocked_tasks"][0]["task_id"] == "bd-b7d2"
                assert data["blocked_tasks"][0]["skip_reason"] == "active_lock"

    def test_queue_plan_with_blocked_tasks(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test queue plan shows blocked tasks with reasons."""
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        blocked = [
            QueueTask(task_id="bd-b7d2", agent="test", skip_reason="active_lock"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks + blocked,
            available_tasks=tasks,
            blocked_tasks=blocked,
            slots_available=1,
            workers_count=1,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue"])

                assert result.exit_code == 0
                assert "Blocked tasks:" in result.output
                assert "bd-b7d2 (agent: test) - active_lock" in result.output

    def test_queue_plan_no_available_tasks(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test queue plan when no tasks available."""
        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue"])

                assert result.exit_code == 0
                assert "No tasks available to start" in result.output


class TestQueueCLIExecution:
    """Execution mode tests (starting tasks)."""

    def test_queue_starts_tasks(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test queue starts tasks with --n."""
        from village.resume import ResumeResult

        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        # Mock successful execution
        def mock_execute(plan, session_name, config):
            return [
                ResumeResult(
                    success=True,
                    task_id=t.task_id,
                    agent=t.agent,
                    worktree_path=config.worktrees_dir / t.task_id,
                    window_name=f"{t.agent}-1-{t.task_id}",
                    pane_id="%12",
                )
                for t in plan.available_tasks
            ]

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                with patch("village.cli.execute_queue_plan", side_effect=mock_execute):
                    result = runner.invoke(village, ["queue", "--n", "2"])

                    assert result.exit_code == 0
                    assert "Starting 2 task(s)..." in result.output
                    assert "Tasks started: 2" in result.output
                    assert "Tasks failed: 0" in result.output

    def test_queue_partial_success_exit_code(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test partial success returns exit code 4."""
        from village.resume import ResumeResult

        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        # Mock mixed results
        def mock_execute(plan, session_name, config):
            return [
                ResumeResult(
                    success=True,
                    task_id=tasks[0].task_id,
                    agent=tasks[0].agent,
                    worktree_path=config.worktrees_dir / tasks[0].task_id,
                    window_name=f"{tasks[0].agent}-1-{tasks[0].task_id}",
                    pane_id="%12",
                ),
                ResumeResult(
                    success=False,
                    task_id=tasks[1].task_id,
                    agent=tasks[1].agent,
                    worktree_path=Path(""),
                    window_name="",
                    pane_id="",
                    error="Failed to create worktree",
                ),
            ]

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                with patch("village.cli.execute_queue_plan", side_effect=mock_execute):
                    result = runner.invoke(village, ["queue", "--n", "2"])

                    assert result.exit_code == 4  # Partial success
                    assert "Tasks started: 1" in result.output
                    assert "Tasks failed: 1" in result.output
                    assert "Failed tasks:" in result.output

    def test_queue_all_failed_exit_code(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test all failed returns exit code 1."""
        from village.resume import ResumeResult

        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=1,
        )

        # Mock all failed
        def mock_execute(plan, session_name, config):
            return [
                ResumeResult(
                    success=False,
                    task_id=t.task_id,
                    agent=t.agent,
                    worktree_path=Path(""),
                    window_name="",
                    pane_id="",
                    error="Failed to create worktree",
                )
                for t in plan.available_tasks
            ]

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                with patch("village.cli.execute_queue_plan", side_effect=mock_execute):
                    result = runner.invoke(village, ["queue", "--n", "1"])

                    assert result.exit_code == 1  # All failed
                    assert "Tasks started: 0" in result.output
                    assert "Tasks failed: 1" in result.output

    def test_queue_json_execution_output(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test JSON execution output."""
        import json

        from village.resume import ResumeResult

        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=1,
        )

        def mock_execute(plan, session_name, config):
            return [
                ResumeResult(
                    success=True,
                    task_id=t.task_id,
                    agent=t.agent,
                    worktree_path=config.worktrees_dir / t.task_id,
                    window_name=f"{t.agent}-1-{t.task_id}",
                    pane_id="%12",
                )
                for t in plan.available_tasks
            ]

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                with patch("village.cli.execute_queue_plan", side_effect=mock_execute):
                    result = runner.invoke(village, ["queue", "--n", "1", "--json"])

                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert data["tasks_started"] == 1
                    assert data["tasks_failed"] == 0
                    assert len(data["results"]) == 1
                    assert data["results"][0]["task_id"] == "bd-a3f8"
                    assert data["results"][0]["success"] is True

    def test_queue_no_tasks_available_exit_code(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test exit code 1 when no tasks available."""

        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue", "--n", "1"])

                assert result.exit_code == EXIT_BLOCKED

    def test_queue_no_tasks_available_json(
        self, runner: click.testing.CliRunner, mock_config: Config
    ):
        """Test JSON output when no tasks available."""
        import json

        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue", "--n", "1", "--json"])

                assert result.exit_code == EXIT_BLOCKED
                data = json.loads(result.output)
                assert data["tasks_started"] == 0
                assert data["tasks_failed"] == 0
                assert data["message"] == "No tasks available to start"


class TestQueueCLIFilters:
    """Filter tests (agent, max-workers)."""

    def test_queue_agent_filter(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test --agent filter works."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=3,
            workers_count=0,
            concurrency_limit=3,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                # Filter to only build tasks
                result = runner.invoke(village, ["queue", "--agent", "build"])

                assert result.exit_code == 0
                # Should show only bd-a3f8
                assert "bd-a3f8 (agent: build)" in result.output
                # Should not show test or worker tasks
                assert "bd-b7d2 (agent: test)" not in result.output
                assert "bd-c4e1 (agent: worker)" not in result.output

    def test_queue_max_workers_override(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test --max-workers overrides config."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                result = runner.invoke(village, ["queue", "--max-workers", "2"])

                assert result.exit_code == 0
                # Should pass max_workers=2 to generate_queue_plan
                from village.cli import generate_queue_plan

                generate_queue_plan.assert_called_once()
                # Extract call args
                call_args = generate_queue_plan.call_args
                assert call_args[0][1] == 2  # max_workers argument

    def test_queue_dry_run(self, runner: click.testing.CliRunner, mock_config: Config):
        """Test --dry-run previews execution."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=1,
        )

        with patch("village.cli.generate_queue_plan", return_value=plan):
            with patch("village.cli.get_config", return_value=mock_config):
                with patch("village.cli.execute_queue_plan") as mock_execute:
                    result = runner.invoke(village, ["queue", "--dry-run", "--n", "1"])

                    assert result.exit_code == 0
                    assert "(dry-run: previewing execution)" in result.output
                    # Should not actually execute
                    mock_execute.assert_not_called()
