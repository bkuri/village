"""Test configuration loader."""

import os
import subprocess
from pathlib import Path

import pytest

from village.config import get_config


def test_get_config_in_git_repo(tmp_path: Path):
    """Test config resolution in git repo."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    assert config.git_root == tmp_path
    assert config.village_dir == tmp_path / ".village"
    assert config.worktrees_dir == tmp_path / ".worktrees"
    assert config.tmux_session == "village"


def test_config_env_vars_override(tmp_path: Path):
    """Test environment variable overrides."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    custom_village = tmp_path / "custom-village"
    os.chdir(tmp_path)
    os.environ["VILLAGE_DIR"] = str(custom_village)

    try:
        config = get_config()
        assert config.village_dir == custom_village
    finally:
        del os.environ["VILLAGE_DIR"]


def test_config_not_in_git_repo(tmp_path: Path):
    """Test error when not in git repo."""
    os.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="Not in a git repository"):
        get_config()


def test_config_ensure_exists(tmp_path: Path):
    """Test creating village directories."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    # Directories shouldn't exist yet
    assert not config.village_dir.exists()

    # Create them
    config.ensure_exists()

    # They should exist now
    assert config.village_dir.exists()
    assert config.locks_dir.exists()
    assert config.worktrees_dir.exists()


def test_config_config_path_property(tmp_path: Path):
    """Test config_path property."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    assert config.config_path == config.village_dir / "config"


def test_config_config_exists(tmp_path: Path):
    """Test config_exists method."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    # Config file doesn't exist
    assert not config.config_exists()

    # Create config file
    config.village_dir.mkdir(parents=True, exist_ok=True)
    config.config_path.touch()

    # Config file exists now
    assert config.config_exists()


def test_config_default_max_workers(tmp_path: Path):
    """Test default max_workers value."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    assert config.max_workers == 2


def test_config_env_max_workers_override(tmp_path: Path):
    """Test VILLAGE_MAX_WORKERS environment variable."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_MAX_WORKERS"] = "5"

    try:
        config = get_config()
        assert config.max_workers == 5
    finally:
        del os.environ["VILLAGE_MAX_WORKERS"]


def test_config_env_max_workers_invalid(tmp_path: Path):
    """Test invalid VILLAGE_MAX_WORKERS uses default."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_MAX_WORKERS"] = "invalid"

    try:
        config = get_config()
        assert config.max_workers == 2
    finally:
        del os.environ["VILLAGE_MAX_WORKERS"]


def test_config_env_max_workers_too_low(tmp_path: Path):
    """Test VILLAGE_MAX_WORKERS < 1 uses default."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_MAX_WORKERS"] = "0"

    try:
        config = get_config()
        assert config.max_workers == 2
    finally:
        del os.environ["VILLAGE_MAX_WORKERS"]


def test_parse_ppc_traits():
    """Test PPC traits parsing."""
    from village.config import _parse_ppc_traits

    # Empty string
    assert _parse_ppc_traits("") == []

    # Single trait
    assert _parse_ppc_traits("conservative") == ["conservative"]

    # Multiple traits
    assert _parse_ppc_traits("conservative,terse,verbose") == ["conservative", "terse", "verbose"]

    # Traits with spaces
    assert _parse_ppc_traits("conservative, terse , verbose") == [
        "conservative",
        "terse",
        "verbose",
    ]

    # Traits with mixed case
    assert _parse_ppc_traits("Conservative,TERSE,Verbose") == ["conservative", "terse", "verbose"]


def test_config_file_empty(tmp_path: Path):
    """Test config file doesn't exist."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    assert config.agents == {}
    assert config.default_agent == "worker"


def test_config_file_with_agents(tmp_path: Path):
    """Test parsing agent configs from file."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    # Create config file
    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[DEFAULT]
DEFAULT_AGENT=build

[agent.build]
opencode_args=--mode patch --safe
contract=contracts/build.md
ppc_mode=build
ppc_traits=conservative,terse
ppc_format=markdown

[agent.test]
opencode_args=--mode patch
ppc_mode=ship
ppc_traits=conservative
ppc_format=code
""")

    os.chdir(tmp_path)
    config = get_config()

    assert config.default_agent == "build"
    assert "build" in config.agents
    assert "test" in config.agents

    # Check build agent config
    build_agent = config.agents["build"]
    assert build_agent.opencode_args == "--mode patch --safe"
    assert build_agent.contract == "contracts/build.md"
    assert build_agent.ppc_mode == "build"
    assert build_agent.ppc_traits == ["conservative", "terse"]
    assert build_agent.ppc_format == "markdown"

    # Check test agent config
    test_agent = config.agents["test"]
    assert test_agent.opencode_args == "--mode patch"
    assert test_agent.contract is None
    assert test_agent.ppc_mode == "ship"
    assert test_agent.ppc_traits == ["conservative"]
    assert test_agent.ppc_format == "code"


def test_config_file_default_ppc_values(tmp_path: Path):
    """Test default PPC values when not specified."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("""[agent.build]
opencode_args=--mode patch
""")

    os.chdir(tmp_path)
    config = get_config()

    build_agent = config.agents["build"]
    assert build_agent.contract is None
    assert build_agent.ppc_mode is None
    assert build_agent.ppc_traits == []
    assert build_agent.ppc_format == "markdown"


def test_config_file_env_default_agent(tmp_path: Path):
    """Test environment variable overrides DEFAULT_AGENT."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("[DEFAULT]\nDEFAULT_AGENT=build")

    os.chdir(tmp_path)
    os.environ["VILLAGE_DEFAULT_AGENT"] = "test"

    try:
        config = get_config()
        assert config.default_agent == "test"
    finally:
        del os.environ["VILLAGE_DEFAULT_AGENT"]


def test_config_queue_ttl_default(tmp_path: Path):
    """Test default queue_ttl_minutes value."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    config = get_config()

    assert config.queue_ttl_minutes == 5


def test_config_queue_ttl_env_override(tmp_path: Path):
    """Test VILLAGE_QUEUE_TTL_MINUTES environment variable."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_QUEUE_TTL_MINUTES"] = "10"

    try:
        config = get_config()
        assert config.queue_ttl_minutes == 10
    finally:
        del os.environ["VILLAGE_QUEUE_TTL_MINUTES"]


def test_config_queue_ttl_file_override(tmp_path: Path):
    """Test config file QUEUE_TTL_MINUTES."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    village_dir = tmp_path / ".village"
    village_dir.mkdir(parents=True, exist_ok=True)
    config_file = village_dir / "config"
    config_file.write_text("[DEFAULT]\nQUEUE_TTL_MINUTES=15")

    os.chdir(tmp_path)
    config = get_config()

    assert config.queue_ttl_minutes == 15


def test_config_queue_ttl_invalid_uses_default(tmp_path: Path):
    """Test invalid VILLAGE_QUEUE_TTL_MINUTES uses default."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_QUEUE_TTL_MINUTES"] = "invalid"

    try:
        config = get_config()
        assert config.queue_ttl_minutes == 5
    finally:
        del os.environ["VILLAGE_QUEUE_TTL_MINUTES"]


def test_config_queue_ttl_negative_uses_default(tmp_path: Path):
    """Test negative VILLAGE_QUEUE_TTL_MINUTES uses default."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)

    os.chdir(tmp_path)
    os.environ["VILLAGE_QUEUE_TTL_MINUTES"] = "-5"

    try:
        config = get_config()
        assert config.queue_ttl_minutes == 5
    finally:
        del os.environ["VILLAGE_QUEUE_TTL_MINUTES"]
