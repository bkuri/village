"""ACP test fixtures and utilities.

Provides mock ACP servers, clients, and test data for comprehensive testing.
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from village.config import Config


@dataclass
class MockACPSession:
    """Mock ACP session data."""

    session_id: str
    cwd: str = "/tmp/test"
    state: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MockACPTerminal:
    """Mock ACP terminal data."""

    terminal_id: str
    session_id: str
    command: str
    output: str = ""
    exit_status: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MockACPConnection:
    """Mock ACP connection for testing."""

    def __init__(self):
        self.sessions: dict[str, MockACPSession] = {}
        self.terminals: dict[str, MockACPTerminal] = {}
        self.initialized = False
        self.calls: list[dict[str, Any]] = []

    async def initialize(self, protocol_version: int = 1, **kwargs):
        """Mock initialize."""
        self.calls.append({"method": "initialize", "protocol_version": protocol_version, **kwargs})
        self.initialized = True
        return {
            "protocol_version": protocol_version,
            "agent_capabilities": {},
            "agent_info": {"name": "mock-agent", "version": "1.0.0"},
        }

    async def new_session(self, cwd: str = ".", **kwargs):
        """Mock new_session."""
        import uuid

        session_id = kwargs.get("session_id") or f"mock-{uuid.uuid4().hex[:8]}"
        self.calls.append({"method": "new_session", "cwd": cwd, "session_id": session_id})
        self.sessions[session_id] = MockACPSession(session_id=session_id, cwd=cwd)
        return {"session_id": session_id}

    async def load_session(self, session_id: str, **kwargs):
        """Mock load_session."""
        self.calls.append({"method": "load_session", "session_id": session_id})
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        return {"session_id": session_id, "state": self.sessions[session_id].state}

    async def prompt(self, session_id: str, prompt: list[Any], **kwargs):
        """Mock prompt."""
        self.calls.append({"method": "prompt", "session_id": session_id, "prompt": prompt})
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        self.sessions[session_id].state = "in_progress"
        return {"stop_reason": "end_turn"}

    async def cancel(self, session_id: str, **kwargs):
        """Mock cancel."""
        self.calls.append({"method": "cancel", "session_id": session_id})
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        self.sessions[session_id].state = "cancelled"

    async def create_terminal(self, session_id: str, command: str, **kwargs):
        """Mock create_terminal."""
        import uuid

        terminal_id = f"term-{uuid.uuid4().hex[:8]}"
        self.calls.append({"method": "create_terminal", "session_id": session_id, "command": command})
        self.terminals[terminal_id] = MockACPTerminal(terminal_id=terminal_id, session_id=session_id, command=command)
        return {"terminal_id": terminal_id}

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs):
        """Mock terminal_output."""
        self.calls.append({"method": "terminal_output", "session_id": session_id, "terminal_id": terminal_id})
        if terminal_id not in self.terminals:
            raise ValueError(f"Terminal not found: {terminal_id}")
        terminal = self.terminals[terminal_id]
        return {"terminal_id": terminal_id, "output": terminal.output}

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs):
        """Mock kill_terminal."""
        self.calls.append({"method": "kill_terminal", "session_id": session_id, "terminal_id": terminal_id})
        if terminal_id in self.terminals:
            del self.terminals[terminal_id]
        return {"terminal_id": terminal_id, "killed": True}

    async def read_text_file(self, path: str, session_id: str, **kwargs):
        """Mock read_text_file."""
        self.calls.append({"method": "read_text_file", "path": path, "session_id": session_id})
        return {"content": "mock file content", "path": path}

    async def write_text_file(self, path: str, content: str, session_id: str, **kwargs):
        """Mock write_text_file."""
        self.calls.append({"method": "write_text_file", "path": path, "session_id": session_id, "content": content})
        return {"success": True, "path": path}


class MockACPServer:
    """Mock ACP server for testing VillageACPClient."""

    def __init__(self):
        self.sessions: dict[str, MockACPSession] = {}
        self.terminals: dict[str, MockACPTerminal] = {}
        self.permissions_requested: list[dict[str, Any]] = []
        self.updates_sent: list[dict[str, Any]] = []

    async def request_permission(self, options: Any, session_id: str, tool_call: Any, **kwargs) -> dict[str, Any]:
        """Mock permission request."""
        self.permissions_requested.append({"options": options, "session_id": session_id, "tool_call": tool_call})
        return {"outcome": {"option_id": "default", "outcome": "selected"}}

    async def session_update(self, session_id: str, update: Any, **kwargs) -> None:
        """Mock session update."""
        self.updates_sent.append({"session_id": session_id, "update": update})

    async def write_text_file(self, content: str, path: str, session_id: str, **kwargs) -> dict[str, Any]:
        """Mock write_text_file (should be denied)."""
        raise PermissionError("File writes not allowed from external agents")

    async def read_text_file(self, path: str, session_id: str, **kwargs) -> dict[str, Any]:
        """Mock read_text_file (should be denied)."""
        raise PermissionError("File reads not allowed from external agents")

    async def create_terminal(self, command: str, session_id: str, **kwargs) -> dict[str, Any]:
        """Mock create_terminal (should be denied)."""
        raise PermissionError("Terminal creation not allowed from external agents")


@pytest.fixture
def mock_acp_connection():
    """Create mock ACP connection."""
    return MockACPConnection()


@pytest.fixture
def mock_acp_server():
    """Create mock ACP server."""
    return MockACPServer()


@pytest.fixture
def acp_config(tmp_path: Path):
    """Create test config for ACP tests."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="test-village",
    )
    config.village_dir.mkdir(parents=True, exist_ok=True)
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def sample_acp_session():
    """Create sample ACP session data."""
    return {
        "sessionId": "test-session-123",
        "cwd": "/tmp/test",
        "message": "Test prompt message",
        "agent": "claude-code",
    }


@pytest.fixture
def sample_acp_events():
    """Create sample ACP events for testing."""
    from village.event_log import Event

    return [
        Event(
            ts="2026-03-05T10:00:00Z",
            cmd="state_transition",
            task_id="test-123",
            result="ok",
        ),
        Event(
            ts="2026-03-05T10:01:00Z",
            cmd="file_modified",
            task_id="test-123",
        ),
        Event(
            ts="2026-03-05T10:02:00Z",
            cmd="conflict_detected",
            task_id="test-123",
            error="Merge conflict in src/main.py",
        ),
        Event(
            ts="2026-03-05T10:03:00Z",
            cmd="queue",
            task_id="test-456",
            result="ok",
        ),
        Event(
            ts="2026-03-05T10:04:00Z",
            cmd="resume",
            task_id="test-456",
            result="error",
            error="Task execution failed",
        ),
    ]


@pytest.fixture
def mock_tmux_session():
    """Mock tmux session operations."""
    mock = MagicMock()

    def mock_create_window(session_name: str, window_name: str, command: str) -> bool:
        return True

    def mock_capture_pane(session_name: str, pane_id: str) -> str:
        return "Mock terminal output"

    def mock_kill_session(target: str) -> bool:
        return True

    mock.create_window = Mock(side_effect=mock_create_window)
    mock.capture_pane = Mock(side_effect=mock_capture_pane)
    mock.kill_session = Mock(side_effect=mock_kill_session)

    return mock


class ACPSessionBuilder:
    """Builder for creating test ACP sessions."""

    def __init__(self):
        self.session_id = "test-session"
        self.cwd = "/tmp/test"
        self.state = "queued"
        self.message = "Test message"
        self.agent = "claude-code"

    def with_session_id(self, session_id: str) -> "ACPSessionBuilder":
        self.session_id = session_id
        return self

    def with_cwd(self, cwd: str) -> "ACPSessionBuilder":
        self.cwd = cwd
        return self

    def with_state(self, state: str) -> "ACPSessionBuilder":
        self.state = state
        return self

    def with_message(self, message: str) -> "ACPSessionBuilder":
        self.message = message
        return self

    def with_agent(self, agent: str) -> "ACPSessionBuilder":
        self.agent = agent
        return self

    def build(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "cwd": self.cwd,
            "state": self.state,
            "message": self.message,
            "agent": self.agent,
        }


class ACPTerminalBuilder:
    """Builder for creating test ACP terminals."""

    def __init__(self):
        self.terminal_id = "test-terminal"
        self.session_id = "test-session"
        self.command = "echo test"
        self.args: list[str] = []
        self.cwd: str | None = None
        self.env: list[Any] = []
        self.output_byte_limit: int | None = None

    def with_terminal_id(self, terminal_id: str) -> "ACPTerminalBuilder":
        self.terminal_id = terminal_id
        return self

    def with_session_id(self, session_id: str) -> "ACPTerminalBuilder":
        self.session_id = session_id
        return self

    def with_command(self, command: str) -> "ACPTerminalBuilder":
        self.command = command
        return self

    def with_args(self, args: list[str]) -> "ACPTerminalBuilder":
        self.args = args
        return self

    def with_cwd(self, cwd: str) -> "ACPTerminalBuilder":
        self.cwd = cwd
        return self

    def with_output_limit(self, limit: int) -> "ACPTerminalBuilder":
        self.output_byte_limit = limit
        return self

    def build(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "terminalId": self.terminal_id,
            "sessionId": self.session_id,
            "command": self.command,
        }
        if self.args:
            result["args"] = self.args
        if self.cwd:
            result["cwd"] = self.cwd
        if self.env:
            result["env"] = self.env
        if self.output_byte_limit:
            result["outputByteLimit"] = self.output_byte_limit
        return result


def create_test_file(path: Path, content: str = "test content") -> Path:
    """Create a test file with content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def create_test_worktree(task_id: str, config: Config, files: dict[str, str] | None = None) -> Path:
    """Create a test worktree with optional files."""
    worktree_path = config.worktrees_dir / task_id
    worktree_path.mkdir(parents=True, exist_ok=True)

    if files:
        for file_path, content in files.items():
            full_path = worktree_path / file_path
            create_test_file(full_path, content)

    return worktree_path


async def wait_for_condition(condition: Any, timeout: float = 5.0, interval: float = 0.1) -> bool:
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False
