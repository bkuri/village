"""Test fixtures for Village Chat."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """Get tmp_path from pytest."""
    return tmp_path


@pytest.fixture
def mock_config(tmp_path: Path) -> _Config:
    """Create a mock config with temp directories."""
    config = Mock(spec=_Config)
    config.village_dir = tmp_path / ".village"
    config.git_root = tmp_path
    config.tmux_session = "test-session"
    return config


@pytest.fixture
def mock_ppc() -> MagicMock:
    """Create mock for PPC subprocess calls."""
    return MagicMock(return_value="PPC v0.2.0")


@pytest.fixture
def mock_fabric() -> MagicMock:
    """Create mock for Fabric subprocess calls."""
    return MagicMock(return_value="Fabric version")


@pytest.fixture
def mock_opencode() -> MagicMock:
    """Create mock for OpenCode subprocess calls."""
    return MagicMock(return_value="LLM response")
