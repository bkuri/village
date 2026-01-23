"""Tests for resume core logic."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from village.config import Config
from village.contracts import ResumeContract
from village.locks import Lock
from village.probes.tools import SubprocessError
from village.resume import (
    ResumeAction,
    ResumeResult,
    _create_resume_window,
    _ensure_worktree_exists,
    _generate_resume_window,
    _get_agent_from_task_id,
    _inject_contract,
    execute_resume,
    is_active_lock,
    plan_resume,
    suggest_next_action,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config."""
    return Config(
        git_root=tmp_path / "repo",
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )


@pytest.fixture
def mock_lock(tmp_path: Path) -> Lock:
    """Create a mock lock."""
    return Lock(
        task_id="bd-a3f8",
        pane_id="%12",
        window="worker-1-bd-a3f8",
        agent="build",
        claimed_at=datetime.now(),
    )


class TestResumeAction:
    """Tests for ResumeAction dataclass."""

    def test_action_creation(self) -> None:
        """Test ResumeAction creation."""
        action = ResumeAction(
            action="resume",
            reason="Ready to resume",
            blocking=False,
            meta={"task_id": "bd-a3f8"},
        )

        assert action.action == "resume"
        assert action.reason == "Ready to resume"
        assert action.blocking is False
        assert action.meta == {"task_id": "bd-a3f8"}


class TestResumeResult:
    """Tests for ResumeResult dataclass."""

    def test_result_creation_success(self) -> None:
        """Test ResumeResult for success."""
        result = ResumeResult(
            success=True,
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            window_name="worker-1-bd-a3f8",
            pane_id="%12",
        )

        assert result.success is True
        assert result.task_id == "bd-a3f8"
        assert result.pane_id == "%12"

    def test_result_creation_failure(self) -> None:
        """Test ResumeResult for failure."""
        result = ResumeResult(
            success=False,
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path(""),
            window_name="",
            pane_id="",
            error="Worktree creation failed",
        )

        assert result.success is False
        assert result.error == "Worktree creation failed"


class TestPlanResume:
    """Tests for plan_resume."""

    def test_plans_up_when_not_initialized(self, mock_config: Config) -> None:
        """Test plan suggests 'up' when not initialized."""
        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="not_ready",
            environment_ready=False,
            runtime_ready=True,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            action = plan_resume(config=mock_config)

            assert action.action == "up"
            assert action.blocking is True
            assert "Village runtime not initialized" in action.reason

    def test_plans_up_when_no_runtime(self, mock_config: Config) -> None:
        """Test plan suggests 'up' when no runtime."""
        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="not_ready",
            environment_ready=True,
            runtime_ready=False,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            action = plan_resume(config=mock_config)

            assert action.action == "up"
            assert action.blocking is True
            assert "Tmux session not running" in action.reason

    def test_plans_cleanup_when_stale_locks(self, mock_config: Config) -> None:
        """Test plan suggests 'cleanup' when stale locks exist."""
        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="ready",
            environment_ready=True,
            runtime_ready=True,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=3,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            action = plan_resume(config=mock_config)

            assert action.action == "cleanup"
            assert action.blocking is False
            assert "stale lock" in action.reason.lower()

    def test_refuses_active_task(self, mock_config: Config) -> None:
        """Test plan refuses to resume task with ACTIVE lock."""
        task_id = "bd-a3f8"

        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="ready",
            environment_ready=True,
            runtime_ready=True,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            with patch("village.resume.parse_lock") as mock_parse_lock:
                with patch("village.resume.is_active_lock") as mock_is_active:
                    mock_parse_lock.return_value = Lock(
                        task_id=task_id,
                        pane_id="%12",
                        window="worker-1-bd-a3f8",
                        agent="build",
                        claimed_at=datetime.now(),
                    )
                    mock_is_active.return_value = True

                    # Create lock file for test
                    lock_path = mock_config.locks_dir / f"{task_id}.lock"
                    lock_path.parent.mkdir(parents=True, exist_ok=True)
                    lock_path.touch()

                    try:
                        action = plan_resume(task_id=task_id, config=mock_config)

                        assert action.action == "status"
                        assert "ACTIVE lock" in action.reason
                    finally:
                        # Clean up lock file
                        if lock_path.exists():
                            lock_path.unlink()

    def test_plans_resume_when_ready(self, mock_config: Config) -> None:
        """Test plan suggests 'resume' when ready."""
        task_id = "bd-a3f8"

        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="ready",
            environment_ready=True,
            runtime_ready=True,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=0,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            action = plan_resume(task_id=task_id, config=mock_config)

            assert action.action == "resume"
            assert action.blocking is False
            assert action.meta["task_id"] == task_id


class TestSuggestNextAction:
    """Tests for suggest_next_action."""

    def test_suggests_queue_when_work_available(
        self,
        mock_config: Config,
    ) -> None:
        """Test suggest queue when work available."""
        from village.ready import ReadyAssessment

        assessment = ReadyAssessment(
            overall="ready",
            environment_ready=True,
            runtime_ready=True,
            work_available="available",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=3,
            suggested_actions=[],
        )

        with patch("village.resume.assess_readiness", return_value=assessment):
            action = suggest_next_action(config=mock_config)

            assert action.action == "queue"

    def test_suggests_ready_when_no_work(self, mock_config: Config) -> None:
        """Test suggest ready when no work available."""
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
            action = suggest_next_action(config=mock_config)

            assert action.action == "ready"


class TestExecuteResume:
    """Tests for execute_resume."""

    def test_executes_resume_successfully(
        self,
        mock_config: Config,
    ) -> None:
        """Test successful resume execution."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            with patch("village.resume._create_resume_window") as mock_create:
                with patch("village.resume.write_lock"):
                    with patch("village.resume._inject_contract"):
                        with patch("village.resume.generate_contract"):
                            mock_ensure.return_value = (
                                Path("/tmp/.worktrees/bd-a3f8"),
                                "worker-1-bd-a3f8",
                                "bd-a3f8",
                            )
                            mock_create.return_value = "%12"

                            result = execute_resume(
                                task_id, agent, detached=False, dry_run=False, config=mock_config
                            )

                            assert result.success is True
                            assert result.task_id == task_id
                            assert result.pane_id == "%12"

    def test_returns_dry_run_result(
        self,
        mock_config: Config,
    ) -> None:
        """Test dry run returns preview result."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            mock_ensure.return_value = (
                Path("/tmp/.worktrees/bd-a3f8"),
                "worker-1-bd-a3f8",
                "bd-a3f8",
            )

            result = execute_resume(
                task_id, agent, detached=False, dry_run=True, config=mock_config
            )

            assert result.success is True
            assert result.pane_id == ""

    def test_handles_worktree_failure(
        self,
        mock_config: Config,
    ) -> None:
        """Test worktree failure returns error result."""
        task_id = "bd-a3f8"
        agent = "build"

        with patch("village.resume._ensure_worktree_exists") as mock_ensure:
            mock_ensure.side_effect = RuntimeError("Worktree creation failed")

            result = execute_resume(
                task_id, agent, detached=False, dry_run=False, config=mock_config
            )

            assert result.success is False
            assert result.error is not None
            assert "Worktree creation failed" in result.error


class TestEnsureWorktreeExists:
    """Tests for _ensure_worktree_exists."""

    def test_creates_worktree_on_first_attempt(
        self,
        mock_config: Config,
    ) -> None:
        """Test worktree created on first attempt."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.resume.get_worktree_info") as mock_get_info:
            with patch("village.resume.create_worktree") as mock_create:
                mock_get_info.return_value = None
                mock_create.return_value = (
                    mock_config.worktrees_dir / task_id,
                    "worker-1-bd-a3f8",
                )

                path, window, final_id = _ensure_worktree_exists(
                    task_id, session_name, dry_run=False, config=mock_config
                )

                assert path == mock_config.worktrees_dir / task_id
                assert final_id == task_id

    def test_uses_existing_worktree(self, mock_config: Config) -> None:
        """Test uses existing worktree."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.resume.get_worktree_info") as mock_get_info:
            from village.worktrees import WorktreeInfo

            mock_get_info.return_value = WorktreeInfo(
                task_id=task_id,
                path=mock_config.worktrees_dir / task_id,
                branch="worktree-bd-a3f8",
                commit="abc123",
            )

            path, window, final_id = _ensure_worktree_exists(
                task_id, session_name, dry_run=False, config=mock_config
            )

            assert path == mock_config.worktrees_dir / task_id

    def test_retries_on_collision(
        self,
        mock_config: Config,
    ) -> None:
        """Test retry on collision."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.resume.get_worktree_info") as mock_get_info:
            with patch("village.resume.create_worktree") as mock_create:
                mock_get_info.return_value = None

                # First attempt fails with collision
                mock_create.side_effect = [
                    SubprocessError("worktree already exists"),
                    (
                        mock_config.worktrees_dir / f"{task_id}-2",
                        f"worker-1-{task_id}-2",
                    ),
                ]

                path, window, final_id = _ensure_worktree_exists(
                    task_id, session_name, dry_run=False, config=mock_config
                )

                assert final_id == f"{task_id}-2"

    def test_fails_after_max_retries(
        self,
        mock_config: Config,
    ) -> None:
        """Test failure after max retries."""
        task_id = "bd-a3f8"
        session_name = "village"

        with patch("village.resume.get_worktree_info") as mock_get_info:
            with patch("village.resume.create_worktree") as mock_create:
                mock_get_info.return_value = None
                mock_create.side_effect = SubprocessError("worktree already exists")

                with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                    _ensure_worktree_exists(
                        task_id, session_name, dry_run=False, config=mock_config
                    )


class TestGenerateResumeWindow:
    """Tests for _generate_resume_window."""

    def test_generates_window_name(self) -> None:
        """Test window name generation."""
        task_id = "bd-a3f8"
        session_name = "village"

        window_name = _generate_resume_window(task_id, session_name)

        assert window_name == f"worker-1-{task_id}"

    def test_handles_task_id_with_suffix(self) -> None:
        """Test task_id with numeric suffix."""
        task_id = "bd-a3f8-2"
        session_name = "village"

        window_name = _generate_resume_window(task_id, session_name)

        assert window_name == "worker-2-bd-a3f8"


class TestCreateResumeWindow:
    """Tests for _create_resume_window."""

    def test_creates_window_successfully(self) -> None:
        """Test successful window creation."""
        session_name = "village"
        window_name = "worker-1-bd-a3f8"

        with patch("village.resume.run_command") as mock_run:
            with patch("village.resume.panes") as mock_panes:
                mock_run.return_value = subprocess.CompletedProcess(
                    ["tmux", "new-window", "-t", "village", "-n", "worker-1-bd-a3f8", "-d"],
                    returncode=0,
                    stdout="",
                    stderr="",
                )
                mock_panes.return_value = {"%10", "%11", "%12"}

                pane_id = _create_resume_window(session_name, window_name, dry_run=False)

                # Any pane from the set is acceptable
                assert pane_id in {"%10", "%11", "%12"}

    def test_returns_empty_on_dry_run(self) -> None:
        """Test returns empty pane ID on dry run."""
        session_name = "village"
        window_name = "worker-1-bd-a3f8"

        pane_id = _create_resume_window(session_name, window_name, dry_run=True)

        assert pane_id == ""

    def test_fails_on_no_panes(self) -> None:
        """Test failure when no panes found."""
        session_name = "village"
        window_name = "worker-1-bd-a3f8"

        with patch("village.resume.run_command"):
            with patch("village.resume.panes") as mock_panes:
                mock_panes.return_value = set()

                with pytest.raises(RuntimeError, match="No panes found"):
                    _create_resume_window(session_name, window_name, dry_run=False)


class TestInjectContract:
    """Tests for _inject_contract."""

    def test_injects_contract(self) -> None:
        """Test contract injection."""
        session_name = "village"
        pane_id = "%12"
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="worker-1-bd-a3f8",
            claimed_at=datetime.now(),
        )

        with patch("village.resume.send_keys") as mock_send:
            with patch("village.resume.format_contract_for_stdin") as mock_format:
                mock_format.return_value = '{"task_id":"bd-a3f8"}'

                _inject_contract(session_name, pane_id, contract, dry_run=False)

                assert mock_send.call_count == 2

    def test_skips_on_dry_run(self) -> None:
        """Test skips injection on dry run."""
        session_name = "village"
        pane_id = "%12"
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="worker-1-bd-a3f8",
            claimed_at=datetime.now(),
        )

        with patch("village.resume.send_keys") as mock_send:
            _inject_contract(session_name, pane_id, contract, dry_run=True)

            mock_send.assert_not_called()


class TestIsActiveLock:
    """Tests for is_active_lock."""

    def test_active_when_pane_exists(self, mock_lock: Lock) -> None:
        """Test active when pane exists."""
        with patch("village.resume.panes") as mock_panes:
            mock_panes.return_value = {"%10", "%11", mock_lock.pane_id}

            is_active = is_active_lock(mock_lock, "village")

            assert is_active is True

    def test_inactive_when_pane_missing(self, mock_lock: Lock) -> None:
        """Test inactive when pane doesn't exist."""
        with patch("village.resume.panes") as mock_panes:
            mock_panes.return_value = {"%10", "%11"}

            is_active = is_active_lock(mock_lock, "village")

            assert is_active is False


class TestGetAgentFromTaskId:
    """Tests for _get_agent_from_task_id."""

    def test_returns_default_agent(self) -> None:
        """Test returns default agent when Beads unavailable."""
        with patch("village.resume.beads_available") as mock_beads:
            mock_beads.side_effect = Exception("Beads unavailable")

            agent = _get_agent_from_task_id("bd-a3f8", default_agent="build")

            assert agent == "build"

    def test_returns_worker_fallback(self) -> None:
        """Test returns 'worker' as fallback."""
        with patch("village.resume.beads_available") as mock_beads:
            mock_beads.side_effect = Exception("Beads unavailable")

            agent = _get_agent_from_task_id("bd-a3f8", default_agent=None)

            assert agent == "worker"
