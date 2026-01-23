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
