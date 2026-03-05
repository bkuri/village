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
async def test_bridge_slice_text_full_content(bridge: ACPBridge):
    """Test _slice_text returns full content when no line/limit."""
    content = "line1\nline2\nline3\nline4\nline5"
    result = bridge._slice_text(content, line=None, limit=None)
    assert result == content


@pytest.mark.asyncio
async def test_bridge_slice_text_with_line(bridge: ACPBridge):
    """Test _slice_text with starting line."""
    content = "line1\nline2\nline3\nline4\nline5"

    # Start from line 2 (1-indexed → 0-indexed)
    result = bridge._slice_text(content, line=2, limit=None)
    lines = result.split("\n")
    assert len(lines) == 4
    assert lines[0] == "line2"


@pytest.mark.asyncio
async def test_bridge_slice_text_with_limit(bridge: ACPBridge):
    """Test _slice_text with limit."""
    content = "line1\nline2\nline3\nline4\nline5"

    # Limit to 1 line from beginning
    result = bridge._slice_text(content, line=None, limit=1)
    lines = result.split("\n")
    assert len(lines) == 1
    assert lines[0] == "line1"


@pytest.mark.asyncio
async def test_bridge_slice_text_with_line_and_limit(bridge: ACPBridge):
    """Test _slice_text with both line and limit."""
    content = "line1\nline2\nline3\nline4\nline5"

    # Start from line 2 (1-indexed), limit to 2 lines
    # This gives lines[1:3] = ["line2", "line3"]
    result = bridge._slice_text(content, line=2, limit=2)
    lines = result.split("\n")
    assert len(lines) == 2
    assert lines[0] == "line2"
    assert lines[1] == "line3"


@pytest.mark.asyncio
async def test_bridge_slice_text_out_of_bounds(bridge: ACPBridge):
    """Test _slice_text handles out of bounds gracefully."""
    content = "line1\nline2\nline3"

    # Line beyond content - should return empty or partial
    result = bridge._slice_text(content, line=9, limit=5)
    assert result == ""

    # Limit beyond content - should return available lines
    result = bridge._slice_text(content, line=0, limit=100)
    lines = result.split("\n")
    assert len(lines) == 3
