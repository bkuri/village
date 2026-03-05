"""Tests for ACP bridge."""

import tempfile
from pathlib import Path

import pytest

from village.acp.bridge import ACPBridge, ACPBridgeError
from village.config import AgentConfig, Config
from village.state_machine import TaskState


@pytest.fixture
def bridge(tmp_path: Path):
    """Create ACP bridge with temp config."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.village_dir.mkdir(parents=True, exist_ok=True)
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Add test agents with correct AgentConfig parameters
    config.agents = {
        "worker": AgentConfig(opencode_args="--test-worker"),
        "build": AgentConfig(opencode_args="--test-build"),
        "test": AgentConfig(opencode_args="--test-test"),
    }

    return ACPBridge(config)


@pytest.mark.asyncio
async def test_bridge_session_new(bridge: ACPBridge):
    """Test creating new ACP session."""
    result = await bridge.session_new({"sessionId": "test-123"})

    assert result["sessionId"] == "test-123"
    assert result["state"] == "queued"


@pytest.mark.asyncio
async def test_bridge_session_new_requires_id(bridge: ACPBridge):
    """Test session/new requires sessionId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.session_new({})


@pytest.mark.asyncio
async def test_bridge_session_load_not_found(bridge: ACPBridge):
    """Test loading non-existent session."""
    with pytest.raises(ACPBridgeError, match="Task not found"):
        await bridge.session_load({"sessionId": "nonexistent"})


@pytest.mark.asyncio
async def test_bridge_session_load_existing(bridge: ACPBridge):
    """Test loading existing session."""
    # Create session first
    await bridge.session_new({"sessionId": "test-456"})

    # Load it
    result = await bridge.session_load({"sessionId": "test-456"})

    assert result["sessionId"] == "test-456"
    assert result["state"] == "queued"


@pytest.mark.asyncio
async def test_bridge_session_cancel(bridge: ACPBridge):
    """Test cancelling session."""
    # Create session
    await bridge.session_new({"sessionId": "test-789"})

    # Manually transition through states to IN_PROGRESS (so we can then transition to PAUSED)
    bridge.state_machine.transition("test-789", TaskState.CLAIMED)
    bridge.state_machine.transition("test-789", TaskState.IN_PROGRESS)

    # Cancel it
    result = await bridge.session_cancel({"sessionId": "test-789"})

    assert result["sessionId"] == "test-789"
    assert result["state"] == "paused"


@pytest.mark.asyncio
async def test_bridge_fs_read_not_in_worktree(bridge: ACPBridge):
    """Test reading file outside worktree fails."""
    with pytest.raises(ACPBridgeError, match="not in Village worktree"):
        await bridge.fs_read_text_file({"path": "/tmp/test.txt"})


@pytest.mark.asyncio
async def test_bridge_fs_write_not_in_worktree(bridge: ACPBridge):
    """Test writing file outside worktree fails."""
    with pytest.raises(ACPBridgeError, match="not in Village worktree"):
        await bridge.fs_write_text_file(
            {
                "path": "/tmp/test.txt",
                "content": "test",
            }
        )


@pytest.mark.asyncio
async def test_bridge_session_set_mode(bridge: ACPBridge):
    """Test setting session mode."""
    # Create session
    await bridge.session_new({"sessionId": "test-mode-1"})

    # Set mode
    result = await bridge.session_set_mode(
        {
            "sessionId": "test-mode-1",
            "mode": "build",
        }
    )

    assert result["sessionId"] == "test-mode-1"
    assert result["mode"] == "build"


@pytest.mark.asyncio
async def test_bridge_session_set_mode_invalid(bridge: ACPBridge):
    """Test setting invalid mode fails."""
    # Create session
    await bridge.session_new({"sessionId": "test-mode-2"})

    # Try invalid mode
    with pytest.raises(ACPBridgeError, match="Invalid mode"):
        await bridge.session_set_mode(
            {
                "sessionId": "test-mode-2",
                "mode": "nonexistent",
            }
        )


@pytest.mark.asyncio
async def test_bridge_session_set_config_option(bridge: ACPBridge):
    """Test setting config option."""
    # Create session
    await bridge.session_new({"sessionId": "test-config-1"})

    # Set config
    result = await bridge.session_set_config_option(
        {
            "sessionId": "test-config-1",
            "key": "temperature",
            "value": "0.7",
        }
    )

    assert result["sessionId"] == "test-config-1"
    assert result["key"] == "temperature"
    assert result["value"] == "0.7"


@pytest.mark.asyncio
async def test_bridge_session_set_config_invalid_key(bridge: ACPBridge):
    """Test setting invalid config key fails."""
    # Create session
    await bridge.session_new({"sessionId": "test-config-2"})

    # Try invalid key
    with pytest.raises(ACPBridgeError, match="Invalid config key"):
        await bridge.session_set_config_option(
            {
                "sessionId": "test-config-2",
                "key": "invalid_key",
                "value": "test",
            }
        )


@pytest.mark.asyncio
async def test_bridge_session_set_model(bridge: ACPBridge):
    """Test setting model."""
    # Create session
    await bridge.session_new({"sessionId": "test-model-1"})

    # Set model
    result = await bridge.session_set_model(
        {
            "sessionId": "test-model-1",
            "model": "claude-3-opus",
        }
    )

    assert result["sessionId"] == "test-model-1"
    assert result["model"] == "claude-3-opus"


@pytest.mark.asyncio
async def test_bridge_session_set_model_missing(bridge: ACPBridge):
    """Test setting model without model param fails."""
    # Create session
    await bridge.session_new({"sessionId": "test-model-2"})

    # Try without model
    with pytest.raises(ACPBridgeError, match="model required"):
        await bridge.session_set_model(
            {
                "sessionId": "test-model-2",
            }
        )
