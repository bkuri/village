"""Test extended lock format with spec metadata."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from village.config import Config
from village.locks import Lock, parse_lock, write_lock


def _make_config(git_root: Path) -> Config:
    return Config(
        git_root=git_root,
        village_dir=git_root / ".village",
        worktrees_dir=git_root / ".worktrees",
    )


def test_lock_with_spec_metadata_write_and_parse(tmp_path: Path):
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = _make_config(tmp_path)

        lock = Lock(
            task_id="001-core-config",
            pane_id="%42",
            window="builder-1-001-core-config",
            agent="worker",
            claimed_at=datetime(2026, 4, 10, 14, 30, 0),
            spec_name="001-core-config.md",
            iteration=2,
            model="zai/glm-5-turbo",
        )

        write_lock(lock)

        parsed = parse_lock(lock.path)
        assert parsed is not None
        assert parsed.task_id == "001-core-config"
        assert parsed.pane_id == "%42"
        assert parsed.agent == "worker"


def test_lock_without_spec_metadata_backward_compat(tmp_path: Path):
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = _make_config(tmp_path)

        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at=datetime(2026, 4, 10, 14, 30, 0),
        )

        write_lock(lock)

        content = lock.path.read_text()
        assert "spec=" not in content
        assert "iteration=" not in content
        assert "model=" not in content

        parsed = parse_lock(lock.path)
        assert parsed is not None
        assert parsed.task_id == "bd-a3f8"


def test_lock_defaults():
    lock = Lock(
        task_id="test",
        pane_id="%1",
        window="test-window",
        agent="worker",
        claimed_at=datetime.now(),
    )
    assert lock.spec_name == ""
    assert lock.iteration == 0
    assert lock.model == ""
