"""Test task store initialization for chat mode."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.chat.initialization import ensure_tasks_initialized, is_tasks_available
from village.config import Config
from village.tasks import TaskStoreError


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create test config with all necessary directories."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="test-session",
        default_agent="worker",
        max_workers=2,
    )
    config.village_dir.mkdir(parents=True, exist_ok=True)
    return config


def test_ensure_tasks_initialized_no_tasks_file(tmp_path: Path, mock_config: Config) -> None:
    assert not (mock_config.village_dir / "tasks.jsonl").exists()

    mock_store = MagicMock()
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        ensure_tasks_initialized(mock_config)

        mock_store.initialize.assert_called_once()


def test_ensure_tasks_initialized_tasks_file_exists(tmp_path: Path, mock_config: Config) -> None:
    (mock_config.village_dir / "tasks.jsonl").touch()

    mock_store = MagicMock()
    mock_store.is_available.return_value = True
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        ensure_tasks_initialized(mock_config)

        mock_store.initialize.assert_called_once()


def test_ensure_tasks_initialized_store_error(tmp_path: Path, mock_config: Config) -> None:
    (mock_config.village_dir / "tasks.jsonl").touch()

    mock_store = MagicMock()
    mock_store.initialize.side_effect = TaskStoreError("init failed")
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        with pytest.raises(TaskStoreError):
            ensure_tasks_initialized(mock_config)


def test_ensure_tasks_initialized_general_exception(tmp_path: Path, mock_config: Config) -> None:
    (mock_config.village_dir / "tasks.jsonl").touch()

    mock_store = MagicMock()
    mock_store.initialize.side_effect = RuntimeError("Unexpected error")
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        with pytest.raises(RuntimeError):
            ensure_tasks_initialized(mock_config)


def test_is_tasks_available_with_tasks_file(tmp_path: Path, mock_config: Config) -> None:
    (mock_config.village_dir / "tasks.jsonl").touch()

    mock_store = MagicMock()
    mock_store.is_available.return_value = True
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        result = is_tasks_available(mock_config)

    assert result is True


def test_is_tasks_available_without_tasks_file(tmp_path: Path, mock_config: Config) -> None:
    assert not (mock_config.village_dir / "tasks.jsonl").exists()

    mock_store = MagicMock()
    mock_store.is_available.return_value = False
    with patch("village.chat.initialization.get_task_store", return_value=mock_store):
        result = is_tasks_available(mock_config)

    assert result is False
