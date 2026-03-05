"""Tests for ACP bridge."""

import tempfile
from pathlib import Path

import pytest

from village.acp.bridge import ACPBridge, ACPBridgeError
from village.config import Config


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

    # Cancel it (from QUEUED state, should transition to FAILED)
    result = await bridge.session_cancel({"sessionId": "test-789"})

    assert result["sessionId"] == "test-789"
    assert result["state"] == "failed"


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


# === Terminal API Tests ===


@pytest.mark.asyncio
async def test_bridge_terminal_create_requires_session_id(bridge: ACPBridge):
    """Test terminal/create requires sessionId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_create({"command": "ls"})


@pytest.mark.asyncio
async def test_bridge_terminal_create_requires_active_task(bridge: ACPBridge):
    """Test terminal/create requires active task."""
    # Create session but don't claim it (not active)
    await bridge.session_new({"sessionId": "test-term-1"})

    with pytest.raises(ACPBridgeError, match="Task not active"):
        await bridge.terminal_create({"sessionId": "test-term-1", "command": "ls"})


@pytest.mark.asyncio
async def test_bridge_terminal_output_requires_ids(bridge: ACPBridge):
    """Test terminal/output requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_output({"terminalId": "term-123"})

    with pytest.raises(ACPBridgeError, match="terminalId required"):
        await bridge.terminal_output({"sessionId": "test-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_output_nonexistent_terminal(bridge: ACPBridge):
    """Test terminal/output fails for nonexistent terminal."""
    with pytest.raises(ACPBridgeError, match="Terminal not found"):
        await bridge.terminal_output({"sessionId": "test-123", "terminalId": "term-999"})


@pytest.mark.asyncio
async def test_bridge_terminal_kill_requires_ids(bridge: ACPBridge):
    """Test terminal/kill requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_kill({"terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_release_requires_ids(bridge: ACPBridge):
    """Test terminal/release requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_release({"terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_wait_requires_ids(bridge: ACPBridge):
    """Test terminal/wait_for_exit requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_wait_for_exit({"terminalId": "term-123"})

    with pytest.raises(ACPBridgeError, match="terminalId required"):
        await bridge.terminal_wait_for_exit({"sessionId": "test-123"})
