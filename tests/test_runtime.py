"""Test runtime lifecycle management."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from village.probes.tools import SubprocessError
from village.runtime import (
    InitializationPlan,
    RuntimeState,
    _create_dashboard,
    _ensure_directories,
    _ensure_session,
    _ensure_tasks_initialized,
    collect_runtime_state,
    execute_initialization,
    plan_initialization,
    shutdown_runtime,
)


def test_collect_runtime_state():
    """Test state collection when session doesn't exist."""
    with patch("village.runtime.session_exists") as mock_session:
        mock_session.return_value = False

        with patch("village.runtime.get_config") as mock_config:
            config_mock = Mock()
            mock_village_dir = MagicMock()
            mock_village_dir.__truediv__ = lambda self, other: MagicMock()
            mock_village_dir.exists.return_value = False
            config_mock.village_dir = mock_village_dir
            config_mock.tmux_session = "village"
            mock_config.return_value = config_mock

            state = collect_runtime_state("village")

            assert state.session_exists is False
            assert state.directories_exist is False
            assert state.session_name == "village"


def test_plan_initialization_all_missing():
    """Test planning when nothing exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=False,
            directories_exist=False,
            tasks_initialized=False,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is True
        assert plan.needs_directories is True
        assert plan.needs_tasks_init is True
        assert plan.session_exists is False
        assert plan.directories_exist is False
        assert plan.tasks_initialized is False


def test_plan_initialization_partial():
    """Test planning when session exists but directories don't."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=False,
            tasks_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is True
        assert plan.needs_tasks_init is False
        assert plan.session_exists is True
        assert plan.directories_exist is False
        assert plan.tasks_initialized is True


def test_plan_initialization_idempotent():
    """Test planning when everything exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=True,
            tasks_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is False
        assert plan.needs_tasks_init is False


def test_ensure_directories_exists():
    """Test _ensure_directories when directory already exists."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Mock()
        config_mock.village_dir.exists.return_value = True
        mock_config.return_value = config_mock

        result = _ensure_directories(dry_run=False)

        assert result is True


def test_ensure_directories_create_success():
    """Test _ensure_directories creating directory successfully."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Mock()
        config_mock.village_dir.exists.return_value = False
        config_mock.ensure_exists = Mock()
        mock_config.return_value = config_mock

        result = _ensure_directories(dry_run=False)

        assert result is True


def test_ensure_directories_dry_run():
    """Test _ensure_directories with dry_run=True."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Mock()
        config_mock.village_dir.exists.return_value = False
        config_mock.ensure_exists = Mock()
        mock_config.return_value = config_mock

        result = _ensure_directories(dry_run=True)

        assert result is False
        config_mock.ensure_exists.assert_not_called()


def test_ensure_tasks_initialized_exists():
    """Test _ensure_tasks_initialized when tasks file already exists."""
    mock_store = MagicMock()
    mock_store.is_available.return_value = True

    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Path("/tmp/.village")
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.tasks.get_task_store", return_value=mock_store):
            result = _ensure_tasks_initialized(dry_run=False)

            assert result is True


def test_ensure_tasks_initialized_success():
    """Test _ensure_tasks_initialized running initialization successfully."""
    mock_store = MagicMock()
    mock_store.is_available.return_value = False

    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Path("/tmp/.village")
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.tasks.get_task_store", return_value=mock_store):
            result = _ensure_tasks_initialized(dry_run=False)

            assert result is True


def test_ensure_tasks_initialized_subprocess_error():
    """Test _ensure_tasks_initialized when initialization fails."""
    mock_store = MagicMock()
    mock_store.is_available.return_value = False
    mock_store.initialize.side_effect = SubprocessError("Command failed")

    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Path("/tmp/.village")
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.tasks.get_task_store", return_value=mock_store):
            with pytest.raises(SubprocessError):
                _ensure_tasks_initialized(dry_run=False)


def test_ensure_tasks_initialized_dry_run():
    """Test _ensure_tasks_initialized with dry_run=True."""
    mock_store = MagicMock()
    mock_store.is_available.return_value = False

    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.village_dir = Path("/tmp/.village")
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.tasks.get_task_store", return_value=mock_store):
            result = _ensure_tasks_initialized(dry_run=True)

            assert result is True
            mock_store.initialize.assert_not_called()


def test_ensure_session_exists():
    """Test _ensure_session when session already exists."""
    with patch("village.config.get_config") as mock_config:
        config_mock = Mock()
        config_mock.tmux_session = "existing_session"
        mock_config.return_value = config_mock

        with patch("village.runtime.session_exists") as mock_exists:
            mock_exists.return_value = True

            result = _ensure_session(dry_run=False)

            assert result is True


def test_ensure_session_create_success():
    """Test _ensure_session creating session successfully."""
    with patch("village.config.get_config") as mock_config:
        config_mock = Mock()
        config_mock.tmux_session = "village"
        mock_config.return_value = config_mock

        with patch("village.runtime.session_exists") as mock_exists:
            mock_exists.return_value = False

            with patch("village.runtime.create_session") as mock_create:
                mock_create.return_value = True

                result = _ensure_session(dry_run=False)

                assert result is True
                mock_create.assert_called_once_with("village")


def test_ensure_session_create_failure():
    """Test _ensure_session when session creation fails."""
    with patch("village.config.get_config") as mock_config:
        config_mock = Mock()
        config_mock.tmux_session = "village"
        mock_config.return_value = config_mock

        with patch("village.runtime.session_exists") as mock_exists:
            mock_exists.return_value = False

            with patch("village.runtime.create_session") as mock_create:
                mock_create.return_value = False

                result = _ensure_session(dry_run=False)

                assert result is False
                mock_create.assert_called_once_with("village")


def test_ensure_session_dry_run():
    """Test _ensure_session with dry_run=True."""
    with patch("village.config.get_config") as mock_config:
        config_mock = Mock()
        config_mock.tmux_session = "village"
        mock_config.return_value = config_mock

        with patch("village.runtime.session_exists") as mock_exists:
            mock_exists.return_value = False

            with patch("village.runtime.create_session") as mock_create:
                result = _ensure_session(dry_run=True)

                assert result is False
                mock_create.assert_not_called()


def test_create_dashboard_exists():
    """Test _create_dashboard when dashboard already exists."""
    with patch("village.runtime.list_windows") as mock_list:
        mock_list.return_value = ["village:dashboard", "other"]

        result = _create_dashboard("test_session", dry_run=False)

        assert result is True


def test_create_dashboard_success():
    """Test _create_dashboard creating dashboard successfully."""
    with patch("village.runtime.list_windows") as mock_list:
        mock_list.return_value = ["other"]

        with patch("village.runtime.create_window") as mock_create:
            mock_create.return_value = True

            result = _create_dashboard("test_session", dry_run=False)

            assert result is True
            mock_create.assert_called_once_with(
                "test_session",
                "village:dashboard",
                "watch -n 2 village watcher status --short",
                cwd=str(Path.cwd()),
            )


def test_create_dashboard_failure():
    """Test _create_dashboard when window creation fails."""
    with patch("village.runtime.list_windows") as mock_list:
        mock_list.return_value = ["other"]

        with patch("village.runtime.create_window") as mock_create:
            mock_create.return_value = False

            result = _create_dashboard("test_session", dry_run=False)

            assert result is False


def test_create_dashboard_dry_run():
    """Test _create_dashboard with dry_run=True."""
    with patch("village.runtime.list_windows") as mock_list:
        mock_list.return_value = ["other"]

        with patch("village.runtime.create_window") as mock_create:
            result = _create_dashboard("test_session", dry_run=True)

            assert result is False
            mock_create.assert_not_called()


def test_execute_initialization_all_steps():
    """Test execute_initialization with all steps needed returns True."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_tasks_init=True,
        session_exists=False,
        directories_exist=False,
        tasks_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_tasks_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        with patch("village.hooks.install_hooks"):
                            config_mock = Mock()
                            config_mock.tmux_session = "village"
                            config_mock.git_root = Path("/git")
                            mock_config.return_value = config_mock

                            result = execute_initialization(plan, dry_run=False, dashboard=True)

                            assert result is True


def test_execute_initialization_partial_steps():
    """Test execute_initialization with some steps already done returns True."""
    plan = InitializationPlan(
        needs_session=False,
        needs_directories=False,
        needs_tasks_init=True,
        session_exists=True,
        directories_exist=True,
        tasks_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_tasks_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        with patch("village.hooks.install_hooks"):
                            config_mock = Mock()
                            config_mock.tmux_session = "village"
                            config_mock.git_root = Path("/git")
                            mock_config.return_value = config_mock

                            result = execute_initialization(plan, dry_run=False, dashboard=True)

                            assert result is True


def test_execute_initialization_no_dashboard():
    """Test execute_initialization with dashboard=False returns True."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_tasks_init=True,
        session_exists=False,
        directories_exist=False,
        tasks_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_tasks_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        with patch("village.hooks.install_hooks"):
                            config_mock = Mock()
                            config_mock.tmux_session = "village"
                            config_mock.git_root = Path("/git")
                            mock_config.return_value = config_mock

                            result = execute_initialization(plan, dry_run=False, dashboard=False)

                            assert result is True


def test_execute_initialization_dry_run():
    """Test execute_initialization with dry_run=True returns True."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_tasks_init=True,
        session_exists=False,
        directories_exist=False,
        tasks_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_tasks_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        with patch("village.hooks.install_hooks"):
                            config_mock = Mock()
                            config_mock.tmux_session = "village"
                            config_mock.git_root = Path("/git")
                            mock_config.return_value = config_mock

                            result = execute_initialization(plan, dry_run=True, dashboard=True)

                            assert result is True


@pytest.mark.parametrize(
    "plan_kwargs, failing_step",
    [
        (
            dict(needs_directories=True, needs_session=True, needs_tasks_init=True),
            "_ensure_directories",
        ),
        (
            dict(needs_directories=False, needs_session=True, needs_tasks_init=True),
            "_ensure_session",
        ),
        (
            dict(needs_directories=False, needs_session=False, needs_tasks_init=True),
            "_ensure_tasks_initialized",
        ),
        (
            dict(needs_directories=False, needs_session=False, needs_tasks_init=False),
            "_create_dashboard",
        ),
    ],
    ids=["directories", "session", "tasks", "dashboard"],
)
def test_execute_initialization_failure_returns_false(plan_kwargs, failing_step):
    """Test execute_initialization returns False when any step fails."""
    plan = InitializationPlan(
        needs_session=plan_kwargs.get("needs_session", False),
        needs_directories=plan_kwargs.get("needs_directories", False),
        needs_tasks_init=plan_kwargs.get("needs_tasks_init", False),
        session_exists=not plan_kwargs.get("needs_session", False),
        directories_exist=not plan_kwargs.get("needs_directories", False),
        tasks_initialized=not plan_kwargs.get("needs_tasks_init", False),
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        with patch("village.runtime._ensure_session") as mock_session:
            with patch("village.runtime._ensure_tasks_initialized") as mock_beads:
                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    with patch("village.runtime.get_config") as mock_config:
                        with patch("village.hooks.install_hooks"):
                            config_mock = Mock()
                            config_mock.tmux_session = "village"
                            config_mock.git_root = Path("/git")
                            mock_config.return_value = config_mock

                            mock_dirs.return_value = failing_step != "_ensure_directories"
                            mock_session.return_value = failing_step != "_ensure_session"
                            mock_beads.return_value = failing_step != "_ensure_tasks_initialized"
                            mock_dashboard.return_value = failing_step != "_create_dashboard"

                            result = execute_initialization(plan, dry_run=False, dashboard=True)

                            assert result is False


def test_shutdown_runtime_success():
    """Test successful session termination."""
    with (
        patch("village.runtime.kill_session") as mock_kill,
        patch("village.runtime.session_exists") as mock_exists,
    ):
        mock_kill.return_value = True
        mock_exists.return_value = True

        success = shutdown_runtime("village")

        assert success is True


def test_shutdown_runtime_no_session():
    """Test graceful handling when session doesn't exist."""
    with (
        patch("village.runtime.kill_session") as mock_kill,
        patch("village.runtime.session_exists") as mock_exists,
    ):
        mock_kill.return_value = True
        mock_exists.return_value = False

        success = shutdown_runtime("village")

        assert success is True


def test_shutdown_runtime_failure():
    """Test shutdown when kill_session fails."""
    with (
        patch("village.runtime.kill_session") as mock_kill,
        patch("village.runtime.session_exists") as mock_exists,
    ):
        mock_kill.return_value = False
        mock_exists.return_value = True

        success = shutdown_runtime("village")

        assert success is False
