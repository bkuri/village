"""Test spec-driven build loop."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from village.config import Config
from village.loop import (
    LoopIteration,
    LoopResult,
    SpecInfo,
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
