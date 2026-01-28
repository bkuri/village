"""Test runtime lifecycle management."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from village.probes.tools import SubprocessError
from village.runtime import (
    InitializationPlan,
    RuntimeState,
    _create_dashboard,
    _ensure_beads_initialized,
    _ensure_directories,
    _ensure_session,
    collect_runtime_state,
    execute_initialization,
    plan_initialization,
    shutdown_runtime,
)


def test_collect_runtime_state():
    """Test state collection when session doesn't exist."""
    subprocess.run(["git", "init"], cwd=Path.cwd(), check=True)
    subprocess.run(["mkdir", "-p", ".village"], cwd=Path.cwd(), check=True)

    with patch("village.probes.tmux.session_exists") as mock_session:
        mock_session.return_value = False

        with patch("village.config.get_config") as mock_config:
            mock_config.return_value = type(
                "Config",
                (),
                {
                    "village_dir": Path.cwd() / ".village",
                    "tmux_session": "village",
                    "beads_dir": Path.cwd() / ".beads",
                },
            )()

            state = collect_runtime_state("village")

            assert state.session_exists is False
            assert state.directories_exist is True
            assert state.beads_initialized is False
            assert state.session_name == "village"


def test_plan_initialization_all_missing():
    """Test planning when nothing exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=False,
            directories_exist=False,
            beads_initialized=False,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is True
        assert plan.needs_directories is True
        assert plan.needs_beads_init is True
        assert plan.session_exists is False
        assert plan.directories_exist is False
        assert plan.beads_initialized is False


def test_plan_initialization_partial():
    """Test planning when session exists but directories don't."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=False,
            beads_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is True
        assert plan.needs_beads_init is False
        assert plan.session_exists is True
        assert plan.directories_exist is False
        assert plan.beads_initialized is True


def test_plan_initialization_idempotent():
    """Test planning when everything exists."""
    with patch("village.runtime.collect_runtime_state") as mock_collect:
        mock_collect.return_value = RuntimeState(
            session_exists=True,
            directories_exist=True,
            beads_initialized=True,
            session_name="village",
        )

        plan = plan_initialization(mock_collect.return_value)

        assert plan.needs_session is False
        assert plan.needs_directories is False
        assert plan.needs_beads_init is False


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
        config_mock.ensure_exists.assert_called_once()


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


def test_ensure_beads_initialized_exists():
    """Test _ensure_beads_initialized when beads already initialized."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.beads_dir = Mock()
        config_mock.beads_dir.exists.return_value = True
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        result = _ensure_beads_initialized(dry_run=False)

        assert result is True


def test_ensure_beads_initialized_success():
    """Test _ensure_beads_initialized running bd init successfully."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.beads_dir = Mock()
        config_mock.beads_dir.exists.return_value = False
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.runtime.run_command") as mock_run:
            result = _ensure_beads_initialized(dry_run=False)

            assert result is True
            mock_run.assert_called_once_with(["bd", "init"], check=True)


def test_ensure_beads_initialized_subprocess_error():
    """Test _ensure_beads_initialized when bd command fails."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.beads_dir = Mock()
        config_mock.beads_dir.exists.return_value = False
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.runtime.run_command") as mock_run:
            mock_run.side_effect = SubprocessError("Command failed")

            result = _ensure_beads_initialized(dry_run=False)

            assert result is True
            mock_run.assert_called_once_with(["bd", "init"], check=True)


def test_ensure_beads_initialized_dry_run():
    """Test _ensure_beads_initialized with dry_run=True."""
    with patch("village.runtime.get_config") as mock_config:
        config_mock = Mock()
        config_mock.beads_dir = Mock()
        config_mock.beads_dir.exists.return_value = False
        config_mock.git_root = Path("/git")
        mock_config.return_value = config_mock

        with patch("village.runtime.run_command") as mock_run:
            result = _ensure_beads_initialized(dry_run=True)

            assert result is False
            mock_run.assert_not_called()


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
                "test_session", "village:dashboard", "watch -n 2 village status --short"
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
    """Test execute_initialization with all steps needed."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=False,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=False, dashboard=True)

                        assert result is True
                        mock_dirs.assert_called_once_with(False)
                        mock_session.assert_called_once_with(False)
                        mock_beads.assert_called_once_with(False)
                        mock_dashboard.assert_called_once_with("village", False)


def test_execute_initialization_partial_steps():
    """Test execute_initialization with some steps already done."""
    plan = InitializationPlan(
        needs_session=False,
        needs_directories=False,
        needs_beads_init=True,
        session_exists=True,
        directories_exist=True,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=False, dashboard=True)

                        assert result is True
                        mock_dirs.assert_not_called()
                        mock_session.assert_not_called()
                        mock_beads.assert_called_once_with(False)
                        mock_dashboard.assert_called_once_with("village", False)


def test_execute_initialization_no_dashboard():
    """Test execute_initialization with dashboard=False."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=False,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=False, dashboard=False)

                        assert result is True
                        mock_dirs.assert_called_once_with(False)
                        mock_session.assert_called_once_with(False)
                        mock_beads.assert_called_once_with(False)
                        mock_dashboard.assert_not_called()


def test_execute_initialization_dry_run():
    """Test execute_initialization with dry_run=True."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=False,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=True, dashboard=True)

                        assert result is True
                        mock_dirs.assert_called_once_with(True)
                        mock_session.assert_called_once_with(True)
                        mock_beads.assert_called_once_with(True)
                        mock_dashboard.assert_called_once_with("village", True)


def test_execute_initialization_failure_directories():
    """Test execute_initialization when directory creation fails."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=False,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = False

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

            with patch("village.runtime._create_dashboard") as mock_dashboard:
                mock_dashboard.return_value = True

                with patch("village.runtime.get_config") as mock_config:
                    config_mock = Mock()
                    config_mock.tmux_session = "village"
                    mock_config.return_value = config_mock

                    result = execute_initialization(plan, dry_run=False, dashboard=True)

                    assert result is False
                    mock_dirs.assert_called_once_with(False)
                    mock_session.assert_not_called()
                    mock_beads.assert_not_called()
                    mock_dashboard.assert_not_called()


def test_execute_initialization_failure_session():
    """Test execute_initialization when session creation fails."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=False,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=True,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = False

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = True

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=False, dashboard=True)

                        assert result is False
                        mock_dirs.assert_not_called()
                        mock_session.assert_called_once_with(False)
                        mock_beads.assert_not_called()
                        mock_dashboard.assert_not_called()


def test_execute_initialization_failure_beads():
    """Test execute_initialization when beads initialization fails."""
    plan = InitializationPlan(
        needs_session=False,
        needs_directories=False,
        needs_beads_init=True,
        session_exists=True,
        directories_exist=True,
        beads_initialized=False,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

            with patch("village.runtime._ensure_beads_initialized") as mock_beads:
                mock_beads.return_value = False

                with patch("village.runtime._create_dashboard") as mock_dashboard:
                    mock_dashboard.return_value = True

                    with patch("village.runtime.get_config") as mock_config:
                        config_mock = Mock()
                        config_mock.tmux_session = "village"
                        mock_config.return_value = config_mock

                        result = execute_initialization(plan, dry_run=False, dashboard=True)

                        assert result is False
                        mock_dirs.assert_not_called()
                        mock_session.assert_not_called()
                        mock_beads.assert_called_once_with(False)
                        mock_dashboard.assert_not_called()


def test_execute_initialization_failure_dashboard():
    """Test execute_initialization when dashboard creation fails."""
    plan = InitializationPlan(
        needs_session=False,
        needs_directories=False,
        needs_beads_init=False,
        session_exists=True,
        directories_exist=True,
        beads_initialized=True,
    )

    with patch("village.runtime._ensure_directories") as mock_dirs:
        mock_dirs.return_value = True

        with patch("village.runtime._ensure_session") as mock_session:
            mock_session.return_value = True

        with patch("village.runtime._ensure_beads_initialized") as mock_beads:
            mock_beads.return_value = True

            with patch("village.runtime._create_dashboard") as mock_dashboard:
                mock_dashboard.return_value = False

                with patch("village.runtime.get_config") as mock_config:
                    config_mock = Mock()
                    config_mock.tmux_session = "village"
                    mock_config.return_value = config_mock

                    result = execute_initialization(plan, dry_run=False, dashboard=True)

                    assert result is False
                    mock_dirs.assert_not_called()
                    mock_session.assert_not_called()
                    mock_beads.assert_not_called()
                    mock_dashboard.assert_called_once_with("village", False)


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
        mock_kill.assert_called_once_with("village")


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
        mock_kill.assert_not_called()


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
        mock_kill.assert_called_once_with("village")
