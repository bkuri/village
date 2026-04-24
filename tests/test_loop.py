"""Test spec-driven build loop."""

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.config import Config
from village.loop import (
    LoopIteration,
    LoopResult,
    SpecInfo,
    _execute_spec,
    _run_parallel_batch,
    check_and_trigger_wave,
    check_landing_trigger,
    check_spec_completion,
    detect_promise,
    find_incomplete_specs,
    find_specs,
)


def _make_config(git_root: Path) -> Config:
    village_dir = git_root / ".village"
    return Config(
        git_root=git_root,
        village_dir=village_dir,
        worktrees_dir=git_root / ".worktrees",
        tmux_session="test-session",
    )


def test_find_specs_empty_dir(tmp_path: Path):
    result = find_specs(tmp_path / "nonexistent")
    assert result == []

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    result = find_specs(specs_dir)
    assert result == []


def test_find_specs_sorted(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "003-third.md").write_text("")
    (specs_dir / "001-first.md").write_text("")
    (specs_dir / "002-second.md").write_text("")

    result = find_specs(specs_dir)
    names = [s.name for s in result]
    assert names == ["001-first.md", "002-second.md", "003-third.md"]


def test_find_specs_non_md_ignored(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "001-first.md").write_text("")
    (specs_dir / "notes.txt").write_text("")
    (specs_dir / "README").write_text("")

    result = find_specs(specs_dir)
    assert len(result) == 1
    assert result[0].name == "001-first.md"


def test_check_spec_completion(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n## Status: COMPLETE\n")
    assert check_spec_completion(spec) is True


def test_check_spec_completion_bold(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n**Status**: COMPLETE\n")
    assert check_spec_completion(spec) is True


def test_check_spec_completion_heading(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n### Status: COMPLETE\n")
    assert check_spec_completion(spec) is True


def test_check_spec_completion_incomplete(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n## Status: incomplete\n")
    assert check_spec_completion(spec) is False


def test_check_spec_completion_missing(tmp_path: Path):
    assert check_spec_completion(tmp_path / "nonexistent.md") is False


def test_check_spec_completion_case_insensitive(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# My Spec\n\n## Status: complete\n")
    assert check_spec_completion(spec) is True


def test_find_incomplete_specs(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "001-done.md").write_text("## Status: COMPLETE\n")
    (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
    (specs_dir / "003-also-done.md").write_text("**Status**: COMPLETE\n")

    result = find_incomplete_specs(specs_dir)
    assert len(result) == 1
    assert result[0].name == "002-todo.md"


def test_find_incomplete_specs_all_complete(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "001-done.md").write_text("## Status: COMPLETE\n")
    (specs_dir / "002-done.md").write_text("## Status: COMPLETE\n")

    result = find_incomplete_specs(specs_dir)
    assert result == []


def test_detect_promise_done(tmp_path: Path):
    assert detect_promise("some output\n<promise>DONE</promise>\nmore") == "<promise>DONE</promise>"


def test_detect_promise_all_done(tmp_path: Path):
    assert detect_promise("output\n<promise>ALL_DONE</promise>\n") == "<promise>ALL_DONE</promise>"


def test_detect_promise_none(tmp_path: Path):
    assert detect_promise("no promise here") is None


def test_detect_promise_empty(tmp_path: Path):
    assert detect_promise("") is None


def test_loop_result_structure():
    result = LoopResult(
        total_specs=5,
        completed_specs=3,
        iterations=4,
        remaining=["004-next.md", "005-last.md"],
    )
    assert result.total_specs == 5
    assert result.completed_specs == 3
    assert result.iterations == 4
    assert len(result.remaining) == 2


def test_loop_iteration_structure():
    it = LoopIteration(
        iteration=1,
        spec_name="001-test.md",
        success=True,
        promise_detected=True,
        verified_complete=True,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        pane_id="%42",
    )
    assert it.iteration == 1
    assert it.spec_name == "001-test.md"
    assert it.success is True
    assert it.pane_id == "%42"


def test_run_loop_no_specs_dir(tmp_path: Path):
    config = _make_config(tmp_path)
    try:
        from village.loop import run_loop

        run_loop(specs_dir=tmp_path / "nonexistent", config=config)
        assert False, "Should have raised"
    except FileNotFoundError:
        pass


def test_run_loop_empty_specs_dir(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    config = _make_config(tmp_path)
    try:
        from village.loop import run_loop

        run_loop(specs_dir=specs_dir, config=config)
        assert False, "Should have raised"
    except ValueError as e:
        assert "No specs found" in str(e)


def test_run_loop_all_complete(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "001-done.md").write_text("## Status: COMPLETE\n")

    config = _make_config(tmp_path)
    with patch("village.loop.get_config", return_value=config):
        from village.loop import run_loop

        result = run_loop(specs_dir=specs_dir, config=config)
    assert result.total_specs == 1
    assert result.completed_specs == 1
    assert result.iterations == 0
    assert result.remaining == []


def test_run_loop_dry_run(tmp_path: Path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")

    config = _make_config(tmp_path)
    from village.loop import run_loop

    result = run_loop(specs_dir=specs_dir, max_iterations=1, dry_run=True, config=config)
    assert result.total_specs == 1
    assert result.completed_specs == 0
    assert result.iterations == 1
    assert len(result.details) == 1
    assert result.details[0].success is True


def test_spec_info_dataclass(tmp_path: Path):
    spec_path = tmp_path / "001-test.md"
    spec_path.write_text("## Status: incomplete\n")
    info = SpecInfo(path=spec_path, name="001-test.md", is_complete=False)
    assert info.path == spec_path
    assert info.name == "001-test.md"
    assert info.is_complete is False


class TestCheckWaveTrigger:
    def test_no_done_tasks_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        with patch("village.tasks.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = []
            mock_get_store.return_value = mock_store
            result = check_and_trigger_wave(config)
        assert result is False

    def test_done_tasks_no_proposals_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Task 1"
        mock_task.labels = ["bump:patch"]
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.stack.waves.evaluate_wave") as mock_evaluate,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_wave = MagicMock()
            mock_wave.proposals = []
            mock_evaluate.return_value = mock_wave
            result = check_and_trigger_wave(config)
        assert result is False

    def test_user_accepts_proposals(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Task 1"
        mock_task.labels = ["bump:patch"]
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.stack.waves.evaluate_wave") as mock_evaluate,
            patch("village.stack.waves.format_wave_summary") as mock_format,
            patch("village.stack.waves.apply_proposals") as mock_apply,
            patch("builtins.input") as mock_input,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_proposal = MagicMock()
            mock_proposal.__dict__ = {"title": "New subtask"}
            mock_wave = MagicMock()
            mock_wave.proposals = [mock_proposal]
            mock_evaluate.return_value = mock_wave
            mock_format.return_value = "Wave summary"
            mock_input.return_value = "yes"
            mock_apply.return_value = [{"id": "tsk-1", "labels": ["bump:patch", "new-label"]}]
            result = check_and_trigger_wave(config)
        assert result is True

    def test_user_rejects_proposals(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Task 1"
        mock_task.labels = ["bump:patch"]
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.stack.waves.evaluate_wave") as mock_evaluate,
            patch("village.stack.waves.format_wave_summary") as mock_format,
            patch("builtins.input") as mock_input,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_proposal = MagicMock()
            mock_wave = MagicMock()
            mock_wave.proposals = [mock_proposal]
            mock_evaluate.return_value = mock_wave
            mock_format.return_value = "Wave summary"
            mock_input.side_effect = ["no", "not needed"]
            result = check_and_trigger_wave(config)
        assert result is False

    def test_user_rejects_with_cant_continue_raises(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Task 1"
        mock_task.labels = ["bump:patch"]
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.stack.waves.evaluate_wave") as mock_evaluate,
            patch("village.stack.waves.format_wave_summary"),
            patch("builtins.input") as mock_input,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_wave = MagicMock()
            mock_wave.proposals = [MagicMock()]
            mock_evaluate.return_value = mock_wave
            mock_input.side_effect = ["no", "cant-continue"]
            with pytest.raises(RuntimeError, match="rejected wave proposals"):
                check_and_trigger_wave(config)

    def test_eof_error_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Task 1"
        mock_task.labels = ["bump:patch"]
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.stack.waves.evaluate_wave") as mock_evaluate,
            patch("village.stack.waves.format_wave_summary"),
            patch("builtins.input", side_effect=EOFError),
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_wave = MagicMock()
            mock_wave.proposals = [MagicMock()]
            mock_evaluate.return_value = mock_wave
            result = check_and_trigger_wave(config)
        assert result is False


class TestCheckLandingTrigger:
    def test_no_tasks_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        with patch("village.tasks.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = []
            mock_get_store.return_value = mock_store
            result = check_landing_trigger(config)
        assert result is False

    def test_not_all_done_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_done = MagicMock()
        mock_done.id = "tsk-1"
        mock_open = MagicMock()
        mock_open.id = "tsk-2"
        with patch("village.tasks.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_tasks.side_effect = [
                [mock_done, mock_open],
                [mock_done],
            ]
            mock_get_store.return_value = mock_store
            result = check_landing_trigger(config)
        assert result is False

    def test_all_done_triggers_landing(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.builder.arrange.arrange_landing") as mock_arrange,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            result = check_landing_trigger(config, landing_dry_run=True)
        assert result is True
        mock_arrange.assert_called_once_with(dry_run=True)

    def test_landing_failure_returns_false(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.builder.arrange.arrange_landing", side_effect=Exception("landing failed")),
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            result = check_landing_trigger(config)
        assert result is False

    def test_landing_with_plan_slug(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_plan = MagicMock()
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.builder.arrange.arrange_landing"),
            patch("village.plans.store.FilePlanStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            mock_plan_store = MagicMock()
            mock_plan_store.get.return_value = mock_plan
            mock_store_cls.return_value = mock_plan_store
            result = check_landing_trigger(config, plan_slug="my-plan", landing_dry_run=True)
        assert result is True
        mock_plan_store.update.assert_called_once()

    def test_landing_plan_update_failure_logged(self) -> None:
        config = _make_config(Path("/tmp"))
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        with (
            patch("village.tasks.get_task_store") as mock_get_store,
            patch("village.builder.arrange.arrange_landing"),
            patch("village.plans.store.FilePlanStore", side_effect=Exception("store error")),
        ):
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            result = check_landing_trigger(config, plan_slug="bad-plan", landing_dry_run=True)
        assert result is True


class TestRunLoop:
    def test_run_loop_parallel_warning(self, tmp_path: Path) -> None:
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)
        with patch("village.loop.get_config", return_value=config):
            result = run_loop(specs_dir=specs_dir, max_iterations=1, dry_run=True, parallel=3, config=config)
        assert result.iterations == 1

    def test_run_loop_max_iterations(self, tmp_path: Path) -> None:
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)
        result = run_loop(specs_dir=specs_dir, max_iterations=2, dry_run=True, config=config)
        assert result.iterations == 2

    def test_run_loop_dry_run_remaining(self, tmp_path: Path) -> None:
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)
        result = run_loop(specs_dir=specs_dir, max_iterations=1, dry_run=True, config=config)
        assert len(result.remaining) == 1
        assert result.remaining[0] == "001-todo.md"

    def test_run_loop_dry_run_multiple_specs(self, tmp_path: Path) -> None:
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)
        result = run_loop(specs_dir=specs_dir, max_iterations=2, dry_run=True, config=config)
        assert result.total_specs == 2
        assert result.iterations == 2

    def test_run_loop_no_config_uses_get_config(self, tmp_path: Path) -> None:
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-done.md").write_text("## Status: COMPLETE\n")
        config = _make_config(tmp_path)
        with patch("village.loop.get_config", return_value=config):
            result = run_loop(specs_dir=specs_dir)
        assert result.total_specs == 1
        assert result.completed_specs == 1


class TestExecuteSpec:
    """Tests for _execute_spec — single-spec execution."""

    def test_dry_run_returns_success(self, tmp_path: Path) -> None:
        """_execute_spec with dry_run=True returns a successful LoopIteration."""
        spec_path = tmp_path / "specs" / "001-todo.md"
        spec_path.parent.mkdir()
        spec_path.write_text("## Status: incomplete\n")
        spec = SpecInfo(path=spec_path, name="001-todo.md", is_complete=False)
        config = _make_config(tmp_path)

        result = _execute_spec(
            spec=spec,
            iteration_num=1,
            agent="worker",
            model=None,
            config=config,
            session_name="test-session",
            dry_run=True,
        )

        assert result.success is True
        assert result.spec_name == "001-todo.md"
        assert result.iteration == 1
        assert result.error == ""

    def test_worktree_exists_runs_full_chain(self, tmp_path: Path) -> None:
        """_execute_spec with dry_run=False skips worktree creation when path exists."""
        spec_path = tmp_path / "specs" / "001-todo.md"
        spec_path.parent.mkdir()
        spec_path.write_text("## Status: incomplete\n")
        spec = SpecInfo(path=spec_path, name="001-todo.md", is_complete=False)
        config = _make_config(tmp_path)

        # Pre-create the worktree directory so create_worktree is skipped
        worktree_path = config.worktrees_dir / "001-todo"
        worktree_path.mkdir(parents=True)

        with (
            patch("village.loop._create_resume_window", return_value="%42"),
            patch("village.loop.write_lock"),
            patch("village.loop.generate_spec_contract", return_value="mock-contract"),
            patch("village.loop._inject_contract"),
            patch(
                "village.loop.monitor_pane",
                return_value=(True, "output\n<promise>DONE</promise>\n"),
            ),
            patch("village.loop.check_spec_completion", return_value=True),
        ):
            result = _execute_spec(
                spec=spec,
                iteration_num=1,
                agent="worker",
                model=None,
                config=config,
                session_name="test-session",
                dry_run=False,
            )

        assert result.success is True
        assert result.pane_id == "%42"
        assert result.promise_detected is True
        assert result.verified_complete is True
        assert result.error == ""

    def test_worktree_creation_failure_returns_error(self, tmp_path: Path) -> None:
        """_execute_spec returns failure when create_worktree raises."""
        spec_path = tmp_path / "specs" / "001-todo.md"
        spec_path.parent.mkdir()
        spec_path.write_text("## Status: incomplete\n")
        spec = SpecInfo(path=spec_path, name="001-todo.md", is_complete=False)
        config = _make_config(tmp_path)

        with patch(
            "village.loop.create_worktree",
            side_effect=RuntimeError("worktree failed"),
        ):
            result = _execute_spec(
                spec=spec,
                iteration_num=1,
                agent="worker",
                model=None,
                config=config,
                session_name="test-session",
                dry_run=False,
            )

        assert result.success is False
        assert "worktree failed" in result.error


class TestParallelBatch:
    """Tests for _run_parallel_batch — batch parallel execution."""

    def test_dry_run_processes_all_specs(self, tmp_path: Path) -> None:
        """_run_parallel_batch with dry_run=True returns a result for every spec."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")

        specs = find_incomplete_specs(specs_dir)
        config = _make_config(tmp_path)

        results = _run_parallel_batch(
            specs=specs,
            base_iteration=1,
            agent="worker",
            model=None,
            config=config,
            parallel=2,
            dry_run=True,
        )

        assert len(results) == 2
        assert all(r.success for r in results)
        spec_names = {r.spec_name for r in results}
        assert spec_names == {"001-todo.md", "002-todo.md"}

    def test_handles_errors_gracefully(self, tmp_path: Path) -> None:
        """_run_parallel_batch captures exceptions from individual specs without crashing."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")

        specs = find_incomplete_specs(specs_dir)
        config = _make_config(tmp_path)

        success_result = LoopIteration(
            iteration=1,
            spec_name="001-todo.md",
            success=True,
            promise_detected=False,
            verified_complete=False,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

        def _mock_execute(
            spec: SpecInfo,
            iteration_num: int,
            agent: str,
            model: str | None,
            config: Config,
            session_name: str,
            dry_run: bool = False,
        ) -> LoopIteration:
            if spec.name == "001-todo.md":
                return success_result
            raise RuntimeError("agent crashed")

        with patch("village.loop._execute_spec", side_effect=_mock_execute):
            results = _run_parallel_batch(
                specs=specs,
                base_iteration=1,
                agent="worker",
                model=None,
                config=config,
                parallel=2,
                dry_run=False,
            )

        assert len(results) == 2
        # One result should be successful, the other should have an error
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1
        assert "agent crashed" in failures[0].error

    def test_respects_parallel_limit(self, tmp_path: Path) -> None:
        """_run_parallel_batch does not exceed the parallel worker count."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        for i in range(4):
            (specs_dir / f"{i + 1:03d}-todo.md").write_text("## Status: incomplete\n")

        specs = find_incomplete_specs(specs_dir)
        config = _make_config(tmp_path)

        # Track concurrent executions
        max_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        def _mock_execute(
            spec: SpecInfo,
            iteration_num: int,
            agent: str,
            model: str | None,
            config: Config,
            session_name: str,
            dry_run: bool = False,
        ) -> LoopIteration:
            nonlocal max_concurrent, current_concurrent
            with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            time.sleep(0.05)  # Brief hold to let threads overlap
            with lock:
                current_concurrent -= 1
            return LoopIteration(
                iteration=iteration_num,
                spec_name=spec.name,
                success=True,
                promise_detected=False,
                verified_complete=False,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )

        with patch("village.loop._execute_spec", side_effect=_mock_execute):
            results = _run_parallel_batch(
                specs=specs,
                base_iteration=1,
                agent="worker",
                model=None,
                config=config,
                parallel=2,
                dry_run=True,
            )

        assert len(results) == 4
        assert max_concurrent <= 2


class TestRunLoopParallel:
    """Tests for run_loop with parallel > 1."""

    def test_parallel_dry_run_processes_multiple_specs(self, tmp_path: Path) -> None:
        """run_loop with parallel=2 and dry_run=True processes specs in parallel batches."""
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)

        result = run_loop(
            specs_dir=specs_dir,
            max_iterations=1,
            dry_run=True,
            parallel=2,
            config=config,
        )

        assert result.total_specs == 2
        assert result.iterations == 2
        assert len(result.details) == 2
        assert all(d.success for d in result.details)
        spec_names = {d.spec_name for d in result.details}
        assert spec_names == {"001-todo.md", "002-todo.md"}

    def test_parallel_dry_run_batches_limited_by_parallel(self, tmp_path: Path) -> None:
        """run_loop with parallel=2 and 3 specs processes one batch of 2 when max_iterations=2."""
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "003-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)

        result = run_loop(
            specs_dir=specs_dir,
            max_iterations=2,
            dry_run=True,
            parallel=2,
            config=config,
        )

        assert result.total_specs == 3
        # With parallel=2 and max_iterations=2, exactly one batch of 2 runs
        assert result.iterations == 2
        assert len(result.details) == 2
        spec_names = {d.spec_name for d in result.details}
        assert spec_names == {"001-todo.md", "002-todo.md"}

    def test_sequential_preserved_with_parallel_one(self, tmp_path: Path) -> None:
        """run_loop with parallel=1 (default) processes specs one at a time."""
        from village.loop import run_loop

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "001-todo.md").write_text("## Status: incomplete\n")
        (specs_dir / "002-todo.md").write_text("## Status: incomplete\n")
        config = _make_config(tmp_path)

        result = run_loop(
            specs_dir=specs_dir,
            max_iterations=2,
            dry_run=True,
            parallel=1,
            config=config,
        )

        assert result.total_specs == 2
        assert result.iterations == 2
        assert len(result.details) == 2
        assert all(d.success for d in result.details)
        # Sequential mode should assign iteration 1 then 2
        assert result.details[0].iteration == 1
        assert result.details[1].iteration == 2
