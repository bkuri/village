"""Test project scaffolding."""

from pathlib import Path
from unittest.mock import Mock, patch

from village.scaffold import (
    ScaffoldPlan,
    ScaffoldResult,
    execute_scaffold,
    is_inside_git_repo,
    plan_scaffold,
)


def test_is_inside_git_repo_true():
    """Test detection when inside a git repo."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="/some/repo\n")
        assert is_inside_git_repo() is True
        mock_run.assert_called_once()


def test_is_inside_git_repo_false():
    """Test detection when not inside a git repo."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=128, stderr="fatal: not a git repository\n")
        assert is_inside_git_repo() is False


def test_is_inside_git_repo_no_git():
    """Test detection when git binary not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert is_inside_git_repo() is False


def test_plan_scaffold():
    """Test scaffold plan generation."""
    plan = plan_scaffold("myproject", Path("/home/user"))

    assert plan.project_dir == Path("/home/user/myproject")
    assert "Create directory" in plan.steps[0]
    assert "git init" in plan.steps[1]
    assert ".gitignore" in plan.steps[2]
    assert "README.md" in plan.steps[3]
    assert "AGENTS.md" in plan.steps[4]
    assert ".village/config" in plan.steps[5]
    assert "bd init" in plan.steps[6]


def test_execute_scaffold_directory_exists(tmp_path: Path):
    """Test execute_scaffold when directory already exists."""
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()

    result = execute_scaffold("existing", tmp_path)

    assert result.success is False
    assert result.error is not None and "already exists" in result.error


def test_execute_scaffold_success(tmp_path: Path):
    """Test successful project scaffolding."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.create_window") as mock_create_window,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []
        mock_create_window.return_value = True

        result = execute_scaffold("newproject", tmp_path, dashboard=True)

        assert result.success is True
        assert result.project_dir == tmp_path / "newproject"
        assert ".gitignore" in result.created
        assert "README.md" in result.created
        assert "AGENTS.md" in result.created
        assert ".village/" in result.created
        assert ".village/config" in result.created

        project_dir = tmp_path / "newproject"
        assert project_dir.exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "AGENTS.md").exists()
        assert (project_dir / ".village").is_dir()
        assert (project_dir / ".village" / "config").exists()
        assert (project_dir / ".village" / "locks").is_dir()
        assert (project_dir / ".worktrees").is_dir()


def test_execute_scaffold_git_init_failure(tmp_path: Path):
    """Test execute_scaffold when git init fails."""
    with patch("subprocess.run") as mock_subprocess:
        mock_subprocess.return_value = Mock(returncode=1, stderr="git init failed")

        result = execute_scaffold("failproject", tmp_path)

        assert result.success is False
        assert result.error is not None and "git init failed" in result.error


def test_execute_scaffold_no_dashboard(tmp_path: Path):
    """Test execute_scaffold with dashboard=False."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("nodashproject", tmp_path, dashboard=False)

        assert result.success is True
        assert not any("dashboard" in item for item in result.created)


def test_execute_scaffold_bd_init_success(tmp_path: Path):
    """Test execute_scaffold when bd init succeeds."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("bdproject", tmp_path)

        assert result.success is True
        assert "bd init" in result.created


def test_execute_scaffold_bd_init_failure_skipped(tmp_path: Path):
    """Test execute_scaffold when bd init fails (should be skipped silently)."""
    call_count = [0]

    def mock_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            return Mock(returncode=1, stderr="bd not found")
        return Mock(returncode=0)

    with (
        patch("subprocess.run", side_effect=mock_run) as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("nobdproject", tmp_path)

        assert result.success is True
        assert "bd init" not in result.created


def test_execute_scaffold_session_already_exists(tmp_path: Path):
    """Test execute_scaffold when tmux session already exists."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.create_window") as mock_create_window,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = True
        mock_list_windows.return_value = []
        mock_create_window.return_value = True

        result = execute_scaffold("existingsession", tmp_path)

        assert result.success is True
        assert not any("tmux session" in item for item in result.created)


def test_execute_scaffold_creates_gitignore_content(tmp_path: Path):
    """Test that .gitignore contains village entries."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("gitignoreproject", tmp_path)

        assert result.success is True
        gitignore_path = tmp_path / "gitignoreproject" / ".gitignore"
        content = gitignore_path.read_text()
        assert ".village/" in content
        assert ".worktrees/" in content
        assert ".beads/" in content


def test_execute_scaffold_creates_config_template(tmp_path: Path):
    """Test that .village/config contains helpful template."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("configproject", tmp_path)

        assert result.success is True
        config_path = tmp_path / "configproject" / ".village" / "config"
        content = config_path.read_text()
        assert "MAX_WORKERS" in content
        assert "DEFAULT_AGENT" in content
        assert "[agent.worker]" in content


def test_execute_scaffold_creates_agents_md(tmp_path: Path):
    """Test that AGENTS.md contains project name."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("agentsproject", tmp_path)

        assert result.success is True
        agents_path = tmp_path / "agentsproject" / "AGENTS.md"
        content = agents_path.read_text()
        assert "agentsproject" in content
        assert "Build, Lint, and Test Commands" in content


def test_execute_scaffold_creates_readme(tmp_path: Path):
    """Test that README.md contains project name."""
    with (
        patch("subprocess.run") as mock_subprocess,
        patch("village.probes.tmux.create_session") as mock_create_session,
        patch("village.probes.tmux.session_exists") as mock_session_exists,
        patch("village.probes.tmux.list_windows") as mock_list_windows,
    ):
        mock_subprocess.return_value = Mock(returncode=0)
        mock_session_exists.return_value = False
        mock_create_session.return_value = True
        mock_list_windows.return_value = []

        result = execute_scaffold("readmeproject", tmp_path)

        assert result.success is True
        readme_path = tmp_path / "readmeproject" / "README.md"
        content = readme_path.read_text()
        assert "readmeproject" in content
        assert "village up" in content
