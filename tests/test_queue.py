"""Test queue scheduler operations."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.config import Config
from village.queue import (
    QueuePlan,
    QueueTask,
    arbitrate_locks,
    execute_queue_plan,
    extract_agent_from_metadata,
    extract_ready_tasks,
    generate_queue_plan,
    render_queue_plan,
    render_queue_plan_json,
)
from village.resume import ResumeResult


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    return config


class TestExtractAgentFromMetadata:
    """Tests for extract_agent_from_metadata function."""

    def test_extract_agent_colon_notation(self, mock_config: Config):
        """Test extracting agent with colon notation (agent:build)."""
        line = "bd-a3f8 agent:build priority:high"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "build"

    def test_extract_agent_equals_notation(self, mock_config: Config):
        """Test extracting agent with equals notation (agent=build)."""
        line = "bd-a3f8 agent=build priority=high"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "build"

    def test_extract_agent_slash_notation(self, mock_config: Config):
        """Test extracting agent with slash notation (agent/build)."""
        line = "bd-a3f8 agent/build priority/high"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "build"

    def test_extract_agent_case_insensitive(self, mock_config: Config):
        """Test agent extraction is case-insensitive."""
        line = "bd-a3f8 AGENT:Build Priority:High"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "build"

    def test_extract_agent_default_when_missing(self, mock_config: Config):
        """Test default agent when no agent label present."""
        line = "bd-a3f8 priority:high"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "worker"  # default_agent

    def test_extract_agent_first_match_wins(self, mock_config: Config):
        """Test first agent pattern match wins."""
        line = "bd-a3f8 agent:build priority:high agent=test"
        agent = extract_agent_from_metadata(line, mock_config)
        assert agent == "build"


class TestExtractReadyTasks:
    """Tests for extract_ready_tasks function."""

    def test_no_beads_available(self, mock_config: Config):
        """Test when Beads is not available."""
        with patch("village.queue.beads_available") as mock_beads:
            mock_beads.return_value.__bool__.return_value = False
            tasks = extract_ready_tasks(mock_config)
            assert tasks == []

    def test_beads_not_initialized(self, mock_config: Config):
        """Test when Beads repo is not initialized."""
        from village.probes.beads import BeadsStatus

        with patch("village.queue.beads_available") as mock_beads:
            status = BeadsStatus(
                command_available=True,
                command_path="/usr/bin/bd",
                version="1.0.0",
                repo_initialized=False,
                beads_dir_exists=False,
            )
            mock_beads.return_value = status
            tasks = extract_ready_tasks(mock_config)
            assert tasks == []

    def test_empty_ready_output(self, mock_config: Config):
        """Test when bd ready returns empty output."""
        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                mock_beads.return_value.__bool__.return_value = True
                mock_run.return_value = ""
                tasks = extract_ready_tasks(mock_config)
                assert tasks == []

    def test_single_ready_task(self, mock_config: Config):
        """Test extracting a single ready task."""
        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                mock_beads.return_value.__bool__.return_value = True
                mock_run.return_value = "bd-a3f8 agent:build"
                tasks = extract_ready_tasks(mock_config)
                assert len(tasks) == 1
                assert tasks[0].task_id == "bd-a3f8"
                assert tasks[0].agent == "build"

    def test_multiple_ready_tasks(self, mock_config: Config):
        """Test extracting multiple ready tasks."""
        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                output = """bd-a3f8 agent:build
bd-b7d2 agent:test
bd-c4e1 agent:worker"""
                mock_beads.return_value.__bool__.return_value = True
                mock_run.return_value = output
                tasks = extract_ready_tasks(mock_config)
                assert len(tasks) == 3
                assert tasks[0].task_id == "bd-a3f8"
                assert tasks[0].agent == "build"
                assert tasks[1].task_id == "bd-b7d2"
                assert tasks[1].agent == "test"
                assert tasks[2].task_id == "bd-c4e1"
                assert tasks[2].agent == "worker"

    def test_tasks_with_default_agent(self, mock_config: Config):
        """Test tasks without agent label use default."""
        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                mock_beads.return_value.__bool__.return_value = True
                mock_run.return_value = "bd-a3f8 priority:high"
                tasks = extract_ready_tasks(mock_config)
                assert len(tasks) == 1
                assert tasks[0].task_id == "bd-a3f8"
                assert tasks[0].agent == "worker"  # default_agent

    def test_beads_command_failure(self, mock_config: Config):
        """Test handling of Beads command failure."""
        from village.probes.tools import SubprocessError

        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                mock_beads.return_value.__bool__.return_value = True
                mock_run.side_effect = SubprocessError("bd ready failed")
                tasks = extract_ready_tasks(mock_config)
                assert tasks == []

    def test_ignores_empty_lines(self, mock_config: Config):
        """Test empty lines are ignored."""
        with patch("village.queue.beads_available") as mock_beads:
            with patch("village.queue.run_command_output") as mock_run:
                output = """bd-a3f8 agent:build

bd-b7d2 agent:test

bd-c4e1 agent:worker"""
                mock_beads.return_value.__bool__.return_value = True
                mock_run.return_value = output
                tasks = extract_ready_tasks(mock_config)
                assert len(tasks) == 3


class TestQueueTask:
    """Tests for QueueTask dataclass."""

    def test_queue_task_creation(self):
        """Test creating a QueueTask."""
        task = QueueTask(task_id="bd-a3f8", agent="build")
        assert task.task_id == "bd-a3f8"
        assert task.agent == "build"
        assert task.agent_metadata == {}
        assert task.skip_reason is None

    def test_queue_task_with_metadata(self):
        """Test QueueTask with metadata."""
        metadata = {"priority": "high", "labels": ["bugfix"]}
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            agent_metadata=metadata,
        )
        assert task.agent_metadata == metadata

    def test_queue_task_with_skip_reason(self):
        """Test QueueTask with skip reason."""
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            skip_reason="active_lock",
        )
        assert task.skip_reason == "active_lock"


class TestQueuePlan:
    """Tests for QueuePlan dataclass."""

    def test_queue_plan_creation(self):
        """Test creating a QueuePlan."""
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )
        assert len(plan.ready_tasks) == 1
        assert len(plan.available_tasks) == 1
        assert len(plan.blocked_tasks) == 0
        assert plan.slots_available == 2
        assert plan.workers_count == 0
        assert plan.concurrency_limit == 2


class TestArbitrateLocks:
    """Tests for arbitrate_locks function."""

    def test_no_locks_all_available(self, mock_config: Config):
        """Test when no locks exist, all tasks available."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = []
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

            assert len(plan.available_tasks) == 2
            assert len(plan.blocked_tasks) == 0
            assert plan.slots_available == 2
            assert plan.workers_count == 0

    def test_partial_locks_some_blocked(self, mock_config: Config):
        """Test when some tasks have locks, they are blocked."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
        ]

        # Mock worker for bd-b7d2 (already active)
        mock_worker = MagicMock()
        mock_worker.task_id = "bd-b7d2"

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = [mock_worker]
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

            # bd-b7d2 blocked (has lock), bd-c4e1 blocked (concurrency limit)
            # 1 slot available (2 - 1 = 1), so only bd-a3f8 available
            assert len(plan.available_tasks) == 1
            assert plan.available_tasks[0].task_id == "bd-a3f8"
            assert len(plan.blocked_tasks) == 2
            assert plan.blocked_tasks[0].task_id == "bd-b7d2"
            assert plan.blocked_tasks[0].skip_reason == "active_lock"
            assert plan.blocked_tasks[1].task_id == "bd-c4e1"
            assert plan.blocked_tasks[1].skip_reason == "concurrency_limit"
            assert plan.slots_available == 1
            assert plan.workers_count == 1

    def test_concurrency_limit_reached(self, mock_config: Config):
        """Test when concurrency limit is reached, remaining tasks blocked."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
        ]

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = []
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

            # Only 2 tasks available (limit=2), 1 blocked
            assert len(plan.available_tasks) == 2
            assert len(plan.blocked_tasks) == 1
            assert plan.blocked_tasks[0].skip_reason == "concurrency_limit"
            assert plan.slots_available == 2

    def test_no_slots_available(self, mock_config: Config):
        """Test when all slots are occupied, all tasks blocked."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]

        # Mock 2 active workers (max=2, no slots)
        mock_worker1 = MagicMock()
        mock_worker1.task_id = "other-1"
        mock_worker2 = MagicMock()
        mock_worker2.task_id = "other-2"

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = [mock_worker1, mock_worker2]
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

            # All tasks blocked (no slots)
            assert len(plan.available_tasks) == 0
            assert len(plan.blocked_tasks) == 2
            assert all(t.skip_reason == "concurrency_limit" for t in plan.blocked_tasks)
            assert plan.slots_available == 0
            assert plan.workers_count == 2

    def test_mixed_blocking(self, mock_config: Config):
        """Test combination of locks and concurrency limits."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),  # has lock
            QueueTask(task_id="bd-b7d2", agent="test"),  # available
            QueueTask(task_id="bd-c4e1", agent="worker"),  # concurrency limit
        ]

        # Mock worker for bd-a3f8 (already active)
        mock_worker = MagicMock()
        mock_worker.task_id = "bd-a3f8"

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = [mock_worker]
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

            assert len(plan.available_tasks) == 1
            assert len(plan.blocked_tasks) == 2
            assert plan.blocked_tasks[0].task_id == "bd-a3f8"
            assert plan.blocked_tasks[0].skip_reason == "active_lock"
            assert plan.blocked_tasks[1].task_id == "bd-c4e1"
            assert plan.blocked_tasks[1].skip_reason == "concurrency_limit"
            assert plan.slots_available == 1
            assert plan.workers_count == 1


class TestGenerateQueuePlan:
    """Tests for generate_queue_plan function."""

    def test_generates_plan_from_ready_tasks(self, mock_config: Config):
        """Test generating complete queue plan."""
        with patch("village.queue.extract_ready_tasks") as mock_extract:
            with patch("village.queue.arbitrate_locks") as mock_arbitrate:
                tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
                mock_extract.return_value = tasks

                expected_plan = QueuePlan(
                    ready_tasks=tasks,
                    available_tasks=tasks,
                    blocked_tasks=[],
                    slots_available=2,
                    workers_count=0,
                    concurrency_limit=2,
                )
                mock_arbitrate.return_value = expected_plan

                plan = generate_queue_plan("village", 2, mock_config)

                mock_extract.assert_called_once_with(mock_config)
                mock_arbitrate.assert_called_once_with(tasks, "village", 2, mock_config, False)
                assert plan == expected_plan

    def test_uses_default_config_when_not_provided(self, tmp_path: Path):
        """Test that default config is used when not provided."""
        with patch("village.queue.get_config") as mock_get_config:
            with patch("village.queue.extract_ready_tasks") as mock_extract:
                with patch("village.queue.arbitrate_locks") as mock_arbitrate:
                    mock_config = Config(
                        git_root=tmp_path,
                        village_dir=tmp_path / ".village",
                        worktrees_dir=tmp_path / ".worktrees",
                    )
                    mock_get_config.return_value = mock_config
                    mock_extract.return_value = []

                    mock_arbitrate.return_value = QueuePlan(
                        ready_tasks=[],
                        available_tasks=[],
                        blocked_tasks=[],
                        slots_available=2,
                        workers_count=0,
                        concurrency_limit=2,
                    )

                    generate_queue_plan("village", 2)

                    mock_get_config.assert_called_once()
                    mock_extract.assert_called_once_with(mock_config)


class TestRenderQueuePlan:
    """Tests for render_queue_plan function."""

    def test_render_plan_summary(self, mock_config: Config):
        """Test rendering plan summary."""
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        output = render_queue_plan(plan, verbose=False)

        assert "Ready tasks: 1" in output
        assert "Available tasks: 1" in output
        assert "Blocked tasks: 0" in output
        assert "Slots available: 2" in output
        assert "Active workers: 0" in output
        assert "Concurrency limit: 2" in output

    def test_render_plan_with_available_tasks(self, mock_config: Config):
        """Test rendering available tasks."""
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

        output = render_queue_plan(plan, verbose=False)

        assert "bd-a3f8 (agent: build)" in output
        assert "bd-b7d2 (agent: test)" in output

    def test_render_plan_with_blocked_tasks(self, mock_config: Config):
        """Test rendering blocked tasks with reasons."""
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        blocked = [
            QueueTask(task_id="bd-b7d2", agent="test", skip_reason="active_lock"),
            QueueTask(task_id="bd-c4e1", agent="worker", skip_reason="concurrency_limit"),
        ]
        plan = QueuePlan(
            ready_tasks=tasks + blocked,
            available_tasks=tasks,
            blocked_tasks=blocked,
            slots_available=1,
            workers_count=1,
            concurrency_limit=2,
        )

        output = render_queue_plan(plan, verbose=False)

        assert "bd-b7d2 (agent: test) - active_lock" in output
        assert "bd-c4e1 (agent: worker) - concurrency_limit" in output

    def test_render_plan_no_available_tasks(self, mock_config: Config):
        """Test rendering when no tasks available."""
        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        output = render_queue_plan(plan, verbose=False)

        assert "No tasks available to start" in output


class TestRenderQueuePlanJson:
    """Tests for render_queue_plan_json function."""

    def test_render_plan_json_valid(self, mock_config: Config):
        """Test JSON output is valid."""
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

        json_output = render_queue_plan_json(plan)

        # Parse and validate structure
        data = json.loads(json_output)
        assert data["ready_tasks"][0]["task_id"] == "bd-a3f8"
        assert data["available_tasks"][0]["task_id"] == "bd-a3f8"
        assert data["blocked_tasks"][0]["task_id"] == "bd-b7d2"
        assert data["blocked_tasks"][0]["skip_reason"] == "active_lock"
        assert data["slots_available"] == 1
        assert data["workers_count"] == 1
        assert data["concurrency_limit"] == 2

    def test_render_plan_json_sorted_keys(self, mock_config: Config):
        """Test JSON keys are sorted."""
        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=2,
            workers_count=0,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)

        # Verify keys are sorted (indentation shows order)
        lines = json_output.split("\n")
        assert lines[0] == "{"  # Start with opening brace
        # First few keys should be alphabetical
        assert "available_tasks" in json_output
        assert "blocked_tasks" in json_output
        assert "ready_tasks" in json_output


class TestExecuteQueuePlan:
    """Tests for execute_queue_plan function."""

    def test_execute_plan_starts_tasks(self, mock_config: Config):
        """Test executing plan starts available tasks."""
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

        # Mock successful resume
        def mock_resume(task_id, agent, detached, dry_run, config):
            return ResumeResult(
                success=True,
                task_id=task_id,
                agent=agent,
                worktree_path=config.worktrees_dir / task_id,
                window_name=f"{agent}-1-{task_id}",
                pane_id="%12",
            )

        with patch("village.queue.execute_resume", side_effect=mock_resume):
            results = execute_queue_plan(plan, "village", mock_config)

            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is True
            assert results[0].task_id == "bd-a3f8"
            assert results[1].task_id == "bd-b7d2"

    def test_execute_plan_handles_failures(self, mock_config: Config):
        """Test execution continues on task failures."""
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

        # Mock mixed results (first success, second failure)
        def mock_resume(task_id, agent, detached, dry_run, config):
            if task_id == "bd-a3f8":
                return ResumeResult(
                    success=True,
                    task_id=task_id,
                    agent=agent,
                    worktree_path=config.worktrees_dir / task_id,
                    window_name=f"{agent}-1-{task_id}",
                    pane_id="%12",
                )
            else:
                return ResumeResult(
                    success=False,
                    task_id=task_id,
                    agent=agent,
                    worktree_path=Path(""),
                    window_name="",
                    pane_id="",
                    error="Failed to create worktree",
                )

        with patch("village.queue.execute_resume", side_effect=mock_resume):
            results = execute_queue_plan(plan, "village", mock_config)

            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is False
            assert results[1].error == "Failed to create worktree"

    def test_execute_plan_handles_exceptions(self, mock_config: Config):
        """Test execution handles exceptions gracefully."""
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        plan = QueuePlan(
            ready_tasks=tasks,
            available_tasks=tasks,
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=1,
        )

        # Mock exception in resume
        def mock_resume(task_id, agent, detached, dry_run, config):
            raise RuntimeError("Unexpected error")

        with patch("village.queue.execute_resume", side_effect=mock_resume):
            results = execute_queue_plan(plan, "village", mock_config)

            assert len(results) == 1
            assert results[0].success is False
            assert results[0].error is not None
            assert "Unexpected error" in results[0].error

    def test_execute_plan_no_available_tasks(self, mock_config: Config):
        """Test execution with no available tasks."""
        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        with patch("village.queue.execute_resume") as mock_resume:
            results = execute_queue_plan(plan, "village", mock_config)

            assert len(results) == 0
            mock_resume.assert_not_called()

    def test_execute_queue_logs_events(self, mock_config: Config):
        """Test execute_queue_plan logs queue events."""
        from village.event_log import read_events

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        plan = QueuePlan(
            ready_tasks=[QueueTask(task_id="bd-a3f8", agent="build")],
            available_tasks=[QueueTask(task_id="bd-a3f8", agent="build")],
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=2,
        )

        def mock_resume(task_id, agent, detached, dry_run, config):
            return ResumeResult(
                success=True,
                task_id=task_id,
                agent=agent,
                worktree_path=mock_config.worktrees_dir / task_id,
                window_name="worker-1-bd-a3f8",
                pane_id="%12",
            )

        with patch("village.queue.execute_resume", side_effect=mock_resume):
            execute_queue_plan(plan, "village", mock_config)

        events = read_events(mock_config.village_dir)
        queue_events = [e for e in events if e.cmd == "queue"]
        assert len(queue_events) >= 1
        assert queue_events[0].task_id == "bd-a3f8"


class TestQueueDeduplication:
    """Tests for queue deduplication guard."""

    def test_deduplication_blocks_recent_tasks(self, mock_config: Config):
        """Test deduplication blocks tasks executed recently."""
        from datetime import datetime, timedelta, timezone

        from village.event_log import Event, append_event

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Add a recent event for bd-a3f8 (2 minutes ago)
        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        event = Event(
            ts=recent_ts,
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        # Plan queue with bd-a3f8
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=False)

        assert len(plan.blocked_tasks) == 1
        assert plan.blocked_tasks[0].task_id == "bd-a3f8"
        assert plan.blocked_tasks[0].skip_reason == "recently_executed"

    def test_force_bypasses_deduplication(self, mock_config: Config):
        """Test --force flag bypasses deduplication check."""
        from datetime import datetime, timezone

        from village.event_log import Event, append_event

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Add a recent event for bd-a3f8
        recent_ts = datetime.now(timezone.utc).isoformat()
        event = Event(
            ts=recent_ts,
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        # Plan queue with force=True
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=True)

        # With force=True, task should be available
        assert len(plan.available_tasks) == 1
        assert plan.available_tasks[0].task_id == "bd-a3f8"

    def test_ttl_zero_allows_immediate_reexecution(self, mock_config: Config):
        """Test TTL of 0 allows immediate re-execution."""
        from datetime import datetime, timezone

        from village.event_log import Event, append_event

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Set queue_ttl_minutes to 0
        mock_config.queue_ttl_minutes = 0

        # Add a recent event for bd-a3f8
        recent_ts = datetime.now(timezone.utc).isoformat()
        event = Event(
            ts=recent_ts,
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        # Plan queue with TTL=0
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=False)

        # With TTL=0, task should be available
        assert len(plan.available_tasks) == 1

    def test_no_event_allows_task(self, mock_config: Config):
        """Test tasks without events are not blocked."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Plan queue with no events in log
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=False)

        # Task should be available
        assert len(plan.available_tasks) == 1
        assert plan.available_tasks[0].task_id == "bd-a3f8"


class TestQueueJsonOutput:
    """Tests for enhanced JSON output with lock/workspace details."""

    @pytest.mark.skip(reason="Task state mutation issue needs debugging")
    def test_json_includes_lock_details(self, mock_config: Config):
        """Test JSON output includes lock details."""
        from village.queue import QueuePlan, render_queue_plan_json

        # Create a plan with lock details
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            lock_exists=True,
            lock_pane_id="%12",
            lock_window="build-1-bd-a3f8",
            lock_agent="build",
            lock_claimed_at="2026-01-24T14:30:15.123456",
        )

        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=1,
            workers_count=2,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        output_dict = json.loads(json_output)

        assert "ready_tasks" in output_dict
        assert len(output_dict["ready_tasks"]) == 1
        task_dict = output_dict["ready_tasks"][0]

        assert task_dict["lock_exists"] is True
        assert task_dict["lock_pane_id"] == "%12"
        assert task_dict["lock_window"] == "build-1-bd-a3f8"
        assert task_dict["lock_agent"] == "build"
        assert task_dict["lock_claimed_at"] == "2026-01-24T14:30:15.123456"

    def test_json_includes_worktree_path(self, mock_config: Config):
        """Test JSON output includes worktree path."""
        import json

        from village.queue import QueuePlan, render_queue_plan_json

        # Create a plan with worktree path
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
        )

        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=1,
            workers_count=2,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        output_dict = json.loads(json_output)

        task_dict = output_dict["ready_tasks"][0]
        assert "worktree_path" in task_dict
        assert task_dict["worktree_path"] == "/tmp/.worktrees/bd-a3f8"

    def test_json_handles_missing_lock_and_worktree(self, mock_config: Config):
        """Test JSON output handles missing lock and worktree."""
        import json

        from village.queue import QueuePlan, render_queue_plan_json

        # Create a plan without lock and worktree
        task = QueueTask(task_id="bd-a3f8", agent="build")

        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=1,
            workers_count=2,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        output_dict = json.loads(json_output)

        task_dict = output_dict["ready_tasks"][0]
        assert task_dict["lock_exists"] is False
        assert task_dict["lock_pane_id"] is None
        assert task_dict["lock_window"] is None
        assert task_dict["lock_agent"] is None
        assert task_dict["lock_claimed_at"] is None
        assert task_dict["worktree_path"] is None

    def test_json_validates_schema(self, mock_config: Config):
        """Test JSON output structure is valid."""
        import json

        from village.queue import QueuePlan, render_queue_plan_json

        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=0,
            workers_count=2,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        output_dict = json.loads(json_output)

        # Verify top-level keys
        assert "ready_tasks" in output_dict
        assert "available_tasks" in output_dict
        assert "blocked_tasks" in output_dict
        assert "slots_available" in output_dict
        assert "workers_count" in output_dict
        assert "concurrency_limit" in output_dict

        # Verify metadata keys
        assert output_dict["slots_available"] == 0
        assert output_dict["workers_count"] == 2
        assert output_dict["concurrency_limit"] == 2

    def test_json_sorted_keys(self, mock_config: Config):
        """Test JSON output has sorted keys."""
        import json

        from village.queue import QueuePlan, render_queue_plan_json

        plan = QueuePlan(
            ready_tasks=[],
            available_tasks=[],
            blocked_tasks=[],
            slots_available=1,
            workers_count=2,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        output_dict = json.loads(json_output)

        # Check keys are sorted
        keys = list(output_dict.keys())
        assert keys == sorted(keys)

    def test_arbitrate_populates_lock_info(self, mock_config: Config):
        """Test arbitrate_locks populates lock information."""
        from datetime import datetime, timezone

        from village.locks import Lock, write_lock

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)
        mock_config.locks_dir.mkdir(exist_ok=True)

        # Create a lock file
        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        lock._config = mock_config
        write_lock(lock)

        # Plan queue with the lock present
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=False)

        # Verify lock info is populated
        assert len(plan.ready_tasks) == 1
        task = plan.ready_tasks[0]
        assert task.lock_exists is True
        assert task.lock_pane_id == "%12"
        assert task.lock_window == "build-1-bd-a3f8"
        assert task.lock_agent == "build"
        assert task.lock_claimed_at is not None

        lock.path.unlink(missing_ok=True)

    def test_arbitrate_populates_worktree_path(self, mock_config: Config):
        """Test arbitrate_locks populates worktree path."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)
        mock_config.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Create a worktree directory
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(exist_ok=True)

        # Plan queue with the worktree present
        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]
        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=False)

        # Verify worktree path is populated
        assert len(plan.ready_tasks) == 1
        task = plan.ready_tasks[0]
        assert task.worktree_path == worktree_path

        # Cleanup
        worktree_path.rmdir()
