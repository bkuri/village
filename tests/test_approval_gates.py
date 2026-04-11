"""Test approval gates for queue."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from village.config import ApprovalConfig, Config
from village.queue import (
    QueuePlan,
    QueueTask,
    arbitrate_locks,
    render_queue_plan,
    render_queue_plan_json,
)
from village.state_machine import TaskState, TaskStateMachine


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    return config


class TestApprovalConfig:
    """Tests for ApprovalConfig parsing."""

    def test_default_values(self):
        """Test default config is disabled with threshold 1."""
        config = ApprovalConfig()
        assert config.enabled is False
        assert config.threshold == 1

    def test_from_config_file_enabled(self):
        """Test parsing enabled from config dict."""
        config = ApprovalConfig.from_env_and_config({"queue.approval_enabled": "true"})
        assert config.enabled is True

    def test_from_config_file_disabled(self):
        """Test parsing disabled from config dict."""
        config = ApprovalConfig.from_env_and_config({"queue.approval_enabled": "false"})
        assert config.enabled is False

    def test_from_config_file_uppercase_key(self):
        """Test parsing with uppercase config key."""
        config = ApprovalConfig.from_env_and_config({"QUEUE.APPROVAL_ENABLED": "yes"})
        assert config.enabled is True

    def test_threshold_from_config(self):
        """Test parsing threshold from config dict."""
        config = ApprovalConfig.from_env_and_config({"queue.approval_threshold": "2"})
        assert config.threshold == 2

    def test_threshold_defaults_to_one(self):
        """Test threshold defaults to 1."""
        config = ApprovalConfig.from_env_and_config({})
        assert config.threshold == 1

    def test_env_override_enabled(self):
        """Test environment variable overrides config."""
        with patch.dict("os.environ", {"VILLAGE_APPROVAL_ENABLED": "true"}):
            config = ApprovalConfig.from_env_and_config({})
            assert config.enabled is True

    def test_env_override_threshold(self):
        """Test environment variable overrides threshold."""
        with patch.dict("os.environ", {"VILLAGE_APPROVAL_THRESHOLD": "3"}):
            config = ApprovalConfig.from_env_and_config({"queue.approval_threshold": "2"})
            assert config.threshold == 3


class TestQueueTaskApprovalFields:
    """Tests for approval fields on QueueTask."""

    def test_default_needs_approval_false(self):
        """Test needs_approval defaults to False."""
        task = QueueTask(task_id="bd-a3f8", agent="build")
        assert task.needs_approval is False

    def test_default_approval_status_none(self):
        """Test approval_status defaults to None."""
        task = QueueTask(task_id="bd-a3f8", agent="build")
        assert task.approval_status is None

    def test_set_needs_approval(self):
        """Test setting needs_approval."""
        task = QueueTask(task_id="bd-a3f8", agent="build", needs_approval=True)
        assert task.needs_approval is True

    def test_set_approval_status(self):
        """Test setting approval_status."""
        task = QueueTask(task_id="bd-a3f8", agent="build", approval_status="approved")
        assert task.approval_status == "approved"


class TestApprovalInArbitrateLocks:
    """Tests for approval gate logic in arbitrate_locks."""

    def test_approval_disabled_tasks_available(self, mock_config: Config):
        """Test tasks pass through when approval is disabled."""
        mock_config.approval = ApprovalConfig(enabled=False, threshold=1)
        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={"priority": "P0"},
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.available_tasks) == 1
        assert plan.available_tasks[0].needs_approval is False

    def test_approval_enabled_blocks_high_priority(self, mock_config: Config):
        """Test high-priority tasks are blocked when approval enabled."""
        mock_config.approval = ApprovalConfig(enabled=True, threshold=1)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)
        mock_config.locks_dir.mkdir(parents=True, exist_ok=True)

        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={"priority": "P1"},
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.blocked_tasks) == 1
        assert plan.blocked_tasks[0].skip_reason == "pending_approval"
        assert plan.blocked_tasks[0].needs_approval is True

    def test_approval_threshold_filters_correctly(self, mock_config: Config):
        """Test only tasks at or below threshold are blocked."""
        mock_config.approval = ApprovalConfig(enabled=True, threshold=0)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)
        mock_config.locks_dir.mkdir(parents=True, exist_ok=True)

        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={"priority": "P0"},
            ),
            QueueTask(
                task_id="bd-b7d2",
                agent="build",
                agent_metadata={"priority": "P2"},
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.blocked_tasks) == 1
        assert plan.blocked_tasks[0].task_id == "bd-a3f8"
        assert len(plan.available_tasks) == 1
        assert plan.available_tasks[0].task_id == "bd-b7d2"

    def test_approved_task_passes_through(self, mock_config: Config):
        """Test tasks with approval_status='approved' pass through."""
        mock_config.approval = ApprovalConfig(enabled=True, threshold=1)
        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={"priority": "P0"},
                approval_status="approved",
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.available_tasks) == 1
        assert plan.available_tasks[0].task_id == "bd-a3f8"

    def test_no_priority_metadata_not_blocked(self, mock_config: Config):
        """Test tasks without priority metadata are not blocked."""
        mock_config.approval = ApprovalConfig(enabled=True, threshold=1)
        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={},
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.available_tasks) == 1

    def test_approval_transitions_state_machine(self, tmp_path: Path):
        """Test approval gate transitions task to PENDING_APPROVAL state."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=tmp_path, check=True)
        config = Config(
            git_root=tmp_path,
            village_dir=tmp_path / ".village",
            worktrees_dir=tmp_path / ".worktrees",
        )
        config.village_dir.mkdir(parents=True, exist_ok=True)
        config.locks_dir.mkdir(parents=True, exist_ok=True)
        config.approval = ApprovalConfig(enabled=True, threshold=1)
        config.queue_ttl_minutes = 0

        sm = TaskStateMachine(config)
        sm.initialize_state("bd-a3f8", TaskState.QUEUED)

        tasks = [
            QueueTask(
                task_id="bd-a3f8",
                agent="build",
                agent_metadata={"priority": "P0"},
            ),
        ]

        with patch("village.status.collect_workers", return_value=[]):
            plan = arbitrate_locks(tasks, "village", 2, config)

        assert len(plan.blocked_tasks) == 1
        state = sm.get_state("bd-a3f8")
        assert state == TaskState.PENDING_APPROVAL


class TestRenderApprovalInPlan:
    """Tests for approval rendering in queue plan."""

    def test_render_needs_approval_flag(self):
        """Test [NEEDS APPROVAL] flag in text output."""
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            needs_approval=True,
        )
        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[task],
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=2,
        )

        output = render_queue_plan(plan)

        assert "bd-a3f8 (agent: build) [NEEDS APPROVAL]" in output

    def test_render_no_flag_when_not_needed(self):
        """Test no flag when approval not needed."""
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            needs_approval=False,
        )
        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[task],
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=2,
        )

        output = render_queue_plan(plan)

        assert "[NEEDS APPROVAL]" not in output

    def test_render_json_includes_approval_fields(self):
        """Test JSON output includes needs_approval and approval_status."""
        task = QueueTask(
            task_id="bd-a3f8",
            agent="build",
            needs_approval=True,
            approval_status="pending",
        )
        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[],
            blocked_tasks=[task],
            slots_available=0,
            workers_count=0,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        data = json.loads(json_output)

        blocked = data["blocked_tasks"][0]
        assert blocked["needs_approval"] is True
        assert blocked["approval_status"] == "pending"

    def test_render_json_approval_defaults(self):
        """Test JSON output approval defaults."""
        task = QueueTask(task_id="bd-a3f8", agent="build")
        plan = QueuePlan(
            ready_tasks=[task],
            available_tasks=[task],
            blocked_tasks=[],
            slots_available=1,
            workers_count=0,
            concurrency_limit=2,
        )

        json_output = render_queue_plan_json(plan)
        data = json.loads(json_output)

        available = data["available_tasks"][0]
        assert available["needs_approval"] is False
        assert available["approval_status"] is None
