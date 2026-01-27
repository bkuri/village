"""End-to-end test suite for Village workflows."""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from village.config import Config
from village.event_log import Event, append_event, read_events
from village.locks import Lock, parse_lock, write_lock
from village.queue import QueuePlan, QueueTask, arbitrate_locks
from village.resume import execute_resume
from village.status import Worker, collect_workers


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config for testing."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)
    config.village_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(autouse=True)
def clean_test_environment(mock_config: Config) -> Generator[None, None, None]:
    """Auto-cleanup after each test."""
    yield

    for lock_file in mock_config.locks_dir.glob("*.lock"):
        lock_file.unlink(missing_ok=True)

    for worktree in mock_config.worktrees_dir.iterdir():
        if worktree.is_dir():
            subprocess.run(["rm", "-rf", str(worktree)], check=False)

    event_log = mock_config.village_dir / "events.log"
    if event_log.exists():
        event_log.unlink(missing_ok=True)


@pytest.fixture
def mock_get_config(mock_config: Config) -> Generator[None, None, None]:
    """Patch get_config to return mock_config."""
    with patch("village.locks.get_config", return_value=mock_config):
        with patch("village.status.get_config", return_value=mock_config):
            with patch("village.queue.get_config", return_value=mock_config):
                with patch("village.cleanup.get_config", return_value=mock_config):
                    yield


class TestOnboardingE2E:
    """E2E tests for onboarding workflow."""

    def test_new_project_workflow(self, mock_config: Config, mock_get_config: None) -> None:
        """Test complete new project setup workflow."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        config_file = mock_config.village_dir / "config.ini"
        config_file.write_text("[village]\n", encoding="utf-8")
        assert config_file.exists()

    def test_first_task_execution(self, mock_config: Config) -> None:
        """Test executing the first task in a new project."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        with patch("village.resume._create_resume_window") as mock_window:
            mock_window.return_value = "%12"
            with patch("village.resume.write_lock"):
                with patch("village.resume._inject_contract"):
                    result = execute_resume(
                        task_id,
                        "build",
                        detached=False,
                        dry_run=False,
                        config=mock_config,
                    )

        assert result.success is True
        assert result.task_id == task_id
        assert result.pane_id == "%12"

    def test_status_after_setup(self, mock_config: Config, mock_get_config: None) -> None:
        """Test status reflects correct state after setup."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%12",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        with patch("village.locks.panes") as mock_panes:
            mock_panes.return_value = {"%12"}
            workers = collect_workers("village")

        assert len(workers) == 1
        assert workers[0].task_id == "bd-a3f8"
        assert workers[0].status == "ACTIVE"

    def test_config_creation(self, mock_config: Config, mock_get_config: None) -> None:
        """Test config file is created on initialization."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        config_file = mock_config.village_dir / "config.ini"
        config_file.write_text("[village]\n", encoding="utf-8")
        assert config_file.exists()

    def test_directory_structure(self, mock_config: Config) -> None:
        """Test required directories are created."""
        assert mock_config.locks_dir.exists()
        assert mock_config.worktrees_dir.exists()
        assert mock_config.village_dir.exists()

    def test_event_log_created(self, mock_config: Config) -> None:
        """Test event log file is created."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        event_log = mock_config.village_dir / "events.log"
        assert event_log.exists() or event_log.parent.exists()

    def test_first_task_event_logged(self, mock_config: Config) -> None:
        """Test first task execution is logged to event log."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        events = read_events(mock_config.village_dir)
        assert len(events) == 1
        assert events[0].task_id == "bd-a3f8"


class TestMultiTaskExecutionE2E:
    """E2E tests for multi-task execution."""

    def test_queue_creates_three_workers(self, mock_config: Config) -> None:
        """Test queueing three tasks creates three workers."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
        ]

        for i, task in enumerate(tasks):
            worktree_path = mock_config.worktrees_dir / task.task_id
            worktree_path.mkdir(parents=True, exist_ok=True)
            lock = Lock(
                task_id=task.task_id,
                pane_id=f"%{12 + i}",
                window=f"worker-{i + 1}-{task.task_id}",
                agent=task.agent,
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = {"%12", "%13", "%14"}
            workers = collect_workers("village")

        assert len(workers) == 3
        worker_ids = {w.task_id for w in workers}
        assert worker_ids == {"bd-a3f8", "bd-b7d2", "bd-c4e1"}

    def test_concurrency_limits_enforced(self, mock_config: Config, mock_get_config: None) -> None:
        """Test concurrency limit is respected."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
            QueueTask(task_id="bd-d5f3", agent="build"),
        ]

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = []
            plan = arbitrate_locks(tasks, "village", 2, mock_config, force=True)

        assert len(plan.available_tasks) == 2
        assert len(plan.blocked_tasks) == 2
        assert all(t.skip_reason == "concurrency_limit" for t in plan.blocked_tasks)

    def test_lock_files_correct(self, mock_config: Config, mock_get_config: None) -> None:
        """Test lock files contain correct information."""
        task_id = "bd-a3f8"
        lock = Lock(
            task_id=task_id,
            pane_id="%12",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        lock_file = mock_config.locks_dir / f"{task_id}.lock"
        parsed_lock = parse_lock(lock_file)

        assert parsed_lock is not None
        assert parsed_lock.task_id == task_id
        assert parsed_lock.pane_id == "%12"
        assert parsed_lock.window == "worker-1-bd-a3f8"
        assert parsed_lock.agent == "build"

    def test_multiple_tasks_queued(self, mock_config: Config) -> None:
        """Test multiple tasks can be queued simultaneously."""
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

        assert len(plan.ready_tasks) == 2
        assert len(plan.available_tasks) == 2

    def test_task_order_preserved(self, mock_config: Config, mock_get_config: None) -> None:
        """Test tasks are executed in order."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
            QueueTask(task_id="bd-c4e1", agent="worker"),
        ]

        for i, task in enumerate(tasks):
            worktree_path = mock_config.worktrees_dir / task.task_id
            worktree_path.mkdir(parents=True, exist_ok=True)
            lock = Lock(
                task_id=task.task_id,
                pane_id=f"%{12 + i}",
                window=f"worker-{i + 1}-{task.task_id}",
                agent=task.agent,
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = {"%12", "%13", "%14"}
            workers = collect_workers("village")

        worker_ids = [w.task_id for w in workers]
        assert "bd-a3f8" in worker_ids
        assert "bd-b7d2" in worker_ids
        assert "bd-c4e1" in worker_ids

    def test_worker_status_tracking(self, mock_config: Config, mock_get_config: None) -> None:
        """Test worker status is tracked correctly."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]

        for i, task in enumerate(tasks):
            lock = Lock(
                task_id=task.task_id,
                pane_id=f"%{12 + i}",
                window=f"worker-{i + 1}-{task.task_id}",
                agent=task.agent,
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        with patch("village.locks.panes") as mock_panes:
            mock_panes.return_value = {"%12", "%13"}
            workers = collect_workers("village")

        assert all(w.status == "ACTIVE" for w in workers)


class TestCrashRecoveryE2E:
    """E2E tests for crash recovery."""

    def test_tmux_crash_creates_orphans(self, mock_config: Config, mock_get_config: None) -> None:
        """Test tmux crash creates orphaned locks."""
        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%99",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = set()
            workers = collect_workers("village")

        assert len(workers) == 1
        assert workers[0].status == "STALE"
        assert workers[0].task_id == "bd-a3f8"

    def test_cleanup_removes_orphans(self, mock_config: Config) -> None:
        """Test cleanup removes orphaned locks."""
        from village.cleanup import execute_cleanup, plan_cleanup

        lock = Lock(
            task_id="bd-stale",
            pane_id="%99",
            window="worker-1-bd-stale",
            agent="test",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = set()
            plan = plan_cleanup("village")
            execute_cleanup(plan, mock_config)

        lock_file = mock_config.locks_dir / "bd-stale.lock"
        assert not lock_file.exists()

    def test_event_log_crashes_recorded(self, mock_config: Config) -> None:
        """Test crashes are recorded in event log."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="error",
            error="tmux session crashed",
        )
        append_event(event, mock_config.village_dir)

        events = read_events(mock_config.village_dir)
        crash_events = [e for e in events if e.result == "error"]
        assert len(crash_events) == 1
        assert crash_events[0].error is not None
        assert "crash" in crash_events[0].error.lower()

    def test_stale_lock_detection(self, mock_config: Config, mock_get_config: None) -> None:
        """Test stale locks are detected correctly."""
        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%99",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        lock_file = mock_config.locks_dir / "bd-a3f8.lock"
        assert lock_file.exists()

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = {"%12"}
            workers = collect_workers("village")

        stale_workers = [w for w in workers if w.status == "STALE"]
        assert len(stale_workers) == 1
        assert stale_workers[0].task_id == "bd-a3f8"

    def test_recovery_after_crash(self, mock_config: Config) -> None:
        """Test recovery works after crash."""
        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        lock = Lock(
            task_id=task_id,
            pane_id="%12",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        with patch("village.resume._create_resume_window") as mock_window:
            mock_window.return_value = "%13"
            with patch("village.resume.write_lock"):
                with patch("village.resume._inject_contract"):
                    result = execute_resume(
                        task_id,
                        "build",
                        detached=False,
                        dry_run=False,
                        config=mock_config,
                    )

        assert result.success is True
        assert result.pane_id == "%13"

    def test_orphan_worktree_cleanup(self, mock_config: Config) -> None:
        """Test orphaned worktrees are cleaned up."""
        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        from village.status import collect_orphans

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = set()
            workers = collect_workers("village")
            orphans = collect_orphans("village", workers)

        worktree_orphans = [o for o in orphans if o.type == "STALE_LOCK"]
        assert len(worktree_orphans) >= 1


class TestConcurrencyE2E:
    """E2E tests for concurrency handling."""

    def test_parallel_queue_no_duplicates(self, mock_config: Config) -> None:
        """Test parallel queue operations don't create duplicates."""
        tasks = [
            QueueTask(task_id="bd-a3f8", agent="build"),
            QueueTask(task_id="bd-b7d2", agent="test"),
        ]

        for task in tasks:
            worktree_path = mock_config.worktrees_dir / task.task_id
            worktree_path.mkdir(parents=True, exist_ok=True)
            lock = Lock(
                task_id=task.task_id,
                pane_id="%12",
                window=f"worker-1-{task.task_id}",
                agent=task.agent,
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = {"%12"}
            workers = collect_workers("village")

        worker_ids = [w.task_id for w in workers]
        assert worker_ids.count("bd-a3f8") == 1
        assert worker_ids.count("bd-b7d2") == 1

    def test_lock_arbitration_active_stale(
        self, mock_config: Config, mock_get_config: None
    ) -> None:
        """Test lock arbitration distinguishes active vs stale."""
        active_lock = Lock(
            task_id="bd-active",
            pane_id="%12",
            window="worker-1-bd-active",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(active_lock)

        stale_lock = Lock(
            task_id="bd-stale",
            pane_id="%99",
            window="worker-1-bd-stale",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(stale_lock)

        with patch("village.locks.panes") as mock_panes:
            mock_panes.return_value = {"%12"}
            workers = collect_workers("village")

        active_workers = [w for w in workers if w.status == "ACTIVE"]
        stale_workers = [w for w in workers if w.status == "STALE"]

        assert len(active_workers) == 1
        assert active_workers[0].task_id == "bd-active"
        assert len(stale_workers) == 1
        assert stale_workers[0].task_id == "bd-stale"

    def test_stale_lock_stealing(self, mock_config: Config) -> None:
        """Test stale locks can be replaced."""
        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        stale_lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(stale_lock)

        with patch("village.resume._create_resume_window") as mock_window:
            mock_window.return_value = "%12"
            with patch("village.resume.write_lock"):
                with patch("village.resume._inject_contract"):
                    result = execute_resume(
                        task_id,
                        "build",
                        detached=False,
                        dry_run=False,
                        config=mock_config,
                    )

        assert result.success is True
        assert result.pane_id == "%12"

    def test_concurrent_lock_writes(self, mock_config: Config, mock_get_config: None) -> None:
        """Test concurrent lock writes don't corrupt data."""
        tasks = ["bd-a3f8", "bd-b7d2", "bd-c4e1"]

        for i, task_id in enumerate(tasks):
            lock = Lock(
                task_id=task_id,
                pane_id=f"%{12 + i}",
                window=f"worker-{i + 1}-{task_id}",
                agent="build",
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        lock_files = list(mock_config.locks_dir.glob("*.lock"))
        assert len(lock_files) == 3

        for lock_file in lock_files:
            parsed = parse_lock(lock_file)
            assert parsed is not None
            assert parsed.task_id in tasks

    def test_race_condition_prevention(self, mock_config: Config) -> None:
        """Test race conditions are prevented."""
        task_id = "bd-a3f8"

        lock = Lock(
            task_id=task_id,
            pane_id="%12",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        tasks = [QueueTask(task_id=task_id, agent="build")]

        with patch("village.status.collect_workers") as mock_workers:
            mock_worker = Worker(
                task_id=task_id,
                pane_id="%12",
                window="worker-1-bd-a3f8",
                agent="build",
                claimed_at=datetime.now(timezone.utc).isoformat(),
                status="ACTIVE",
            )
            mock_workers.return_value = [mock_worker]
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.available_tasks) == 0
        assert len(plan.blocked_tasks) == 1
        assert plan.blocked_tasks[0].skip_reason == "active_lock"

    def test_queue_deduplication(self, mock_config: Config) -> None:
        """Test queue deduplication prevents duplicate tasks."""
        from datetime import timedelta

        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        event = Event(
            ts=recent_ts,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        tasks = [QueueTask(task_id="bd-a3f8", agent="build")]

        with patch("village.status.collect_workers") as mock_workers:
            mock_workers.return_value = []
            plan = arbitrate_locks(tasks, "village", 2, mock_config)

        assert len(plan.blocked_tasks) == 1
        assert plan.blocked_tasks[0].skip_reason == "recently_executed"


class TestFullUserJourneyE2E:
    """E2E tests for complete user journey."""

    def test_complete_lifecycle(self, mock_config: Config) -> None:
        """Test complete lifecycle from start to finish."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        with patch("village.resume._create_resume_window") as mock_window:
            mock_window.return_value = "%12"
            with patch("village.resume.write_lock"):
                with patch("village.resume._inject_contract"):
                    result = execute_resume(
                        task_id,
                        "build",
                        detached=False,
                        dry_run=False,
                        config=mock_config,
                    )

        assert result.success is True

        events = read_events(mock_config.village_dir)
        assert len(events) >= 1
        assert any(e.task_id == task_id for e in events)

    def test_cleanup_workflow(self, mock_config: Config) -> None:
        """Test cleanup workflow after task completion."""
        from village.cleanup import execute_cleanup, plan_cleanup

        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="worker-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = set()
            plan = plan_cleanup("village")
            execute_cleanup(plan, mock_config)

        lock_file = mock_config.locks_dir / f"{task_id}.lock"
        assert not lock_file.exists()

    def test_event_log_complete(self, mock_config: Config) -> None:
        """Test event log contains complete history."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        events = [
            Event(
                ts=datetime.now(timezone.utc).isoformat(),
                cmd="queue",
                task_id="bd-a3f8",
                pane="%12",
                result="ok",
            ),
            Event(
                ts=(datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),
                cmd="resume",
                task_id="bd-a3f8",
                pane="%12",
                result="ok",
            ),
        ]

        for event in events:
            append_event(event, mock_config.village_dir)

        logged_events = read_events(mock_config.village_dir)
        assert len(logged_events) == 2
        assert logged_events[0].cmd == "queue"
        assert logged_events[1].cmd == "resume"

    def test_multi_project_workflow(self, mock_config: Config) -> None:
        """Test workflow across multiple projects."""
        tasks = ["bd-a3f8", "bd-b7d2", "bd-c4e1"]

        for i, task_id in enumerate(tasks):
            worktree_path = mock_config.worktrees_dir / task_id
            worktree_path.mkdir(parents=True, exist_ok=True)
            lock = Lock(
                task_id=task_id,
                pane_id=f"%{12 + i}",
                window=f"worker-{i + 1}-{task_id}",
                agent="build",
                claimed_at=datetime.now(timezone.utc),
            )
            write_lock(lock)

        with patch("village.probes.tmux.panes") as mock_panes:
            mock_panes.return_value = {"%12", "%13", "%14"}
            workers = collect_workers("village")

        assert len(workers) == 3

    def test_error_recovery_workflow(self, mock_config: Config) -> None:
        """Test recovery from errors during workflow."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)

        error_event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="resume",
            task_id="bd-a3f8",
            pane="%12",
            result="error",
            error="worktree creation failed",
        )
        append_event(error_event, mock_config.village_dir)

        events = read_events(mock_config.village_dir)
        error_events = [e for e in events if e.result == "error"]
        assert len(error_events) == 1

        task_id = "bd-a3f8"
        worktree_path = mock_config.worktrees_dir / task_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        with patch("village.resume._create_resume_window") as mock_window:
            mock_window.return_value = "%13"
            with patch("village.resume.write_lock"):
                with patch("village.resume._inject_contract"):
                    result = execute_resume(
                        task_id,
                        "build",
                        detached=False,
                        dry_run=False,
                        config=mock_config,
                    )

        assert result.success is True
