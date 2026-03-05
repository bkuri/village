"""Tests for VillageACPClient - ACP Client implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from village.acp.external_client import (
    VillageACPClient,
    spawn_acp_agent,
    test_acp_agent,
)
from village.config import Config


@pytest.fixture
def client():
    """Create VillageACPClient instance."""
    return VillageACPClient()


@pytest.mark.asyncio
class TestVillageACPClientInit:
    """Test VillageACPClient initialization."""

    async def test_client_created(self):
        """Test client can be created."""
        client = VillageACPClient()
        assert client is not None


@pytest.mark.asyncio
class TestRequestPermission:
    """Test request_permission method."""

    async def test_request_permission_auto_approves(self, client: VillageACPClient):
        """Test request_permission auto-approves by default."""
        from acp.schema import AllowedOutcome

        result = await client.request_permission(
            options={},
            session_id="test-session",
            tool_call={"tool": "test"},
        )

        assert result.outcome.option_id == "default"
        assert result.outcome.outcome == "selected"

    async def test_request_permission_with_tool_call(self, client: VillageACPClient):
        """Test request_permission receives tool call info."""
        tool_call = {"tool": "read_file", "path": "/tmp/test.txt"}

        result = await client.request_permission(
            options={},
            session_id="test-session",
            tool_call=tool_call,
        )

        assert result is not None

    async def test_request_permission_with_options(self, client: VillageACPClient):
        """Test request_permission receives options."""
        options = {"allow": ["read", "write"], "deny": ["delete"]}

        result = await client.request_permission(
            options=options,
            session_id="test-session",
            tool_call={},
        )

        assert result is not None

    async def test_request_permission_with_kwargs(self, client: VillageACPClient):
        """Test request_permission accepts additional kwargs."""
        result = await client.request_permission(
            options={},
            session_id="test-session",
            tool_call={},
            extra_param="ignored",
        )

        assert result is not None


@pytest.mark.asyncio
class TestSessionUpdate:
    """Test session_update method."""

    async def test_session_update_no_error(self, client: VillageACPClient):
        """Test session_update handles updates without error."""
        update = {"type": "state_change", "state": "in_progress"}

        await client.session_update(
            session_id="test-session",
            update=update,
        )

    async def test_session_update_with_various_types(self, client: VillageACPClient):
        """Test session_update handles various update types."""
        updates = [
            {"type": "state_change", "state": "in_progress"},
            {"type": "file_change", "path": "/tmp/test.txt"},
            {"type": "error", "error": "Test error"},
            {"type": "lifecycle", "event": "queue"},
        ]

        for update in updates:
            await client.session_update(
                session_id="test-session",
                update=update,
            )

    async def test_session_update_with_kwargs(self, client: VillageACPClient):
        """Test session_update accepts additional kwargs."""
        await client.session_update(
            session_id="test-session",
            update={},
            extra_param="ignored",
        )


@pytest.mark.asyncio
class TestWriteTextFile:
    """Test write_text_file method."""

    async def test_write_text_file_denied(self, client: VillageACPClient):
        """Test write_text_file is denied by default."""
        with pytest.raises(PermissionError, match="File writes not allowed"):
            await client.write_text_file(
                content="test content",
                path="/tmp/test.txt",
                session_id="test-session",
            )

    async def test_write_text_file_with_kwargs(self, client: VillageACPClient):
        """Test write_text_file rejects even with kwargs."""
        with pytest.raises(PermissionError):
            await client.write_text_file(
                content="test",
                path="/tmp/test.txt",
                session_id="test-session",
                extra_param="ignored",
            )


@pytest.mark.asyncio
class TestReadTextFile:
    """Test read_text_file method."""

    async def test_read_text_file_denied(self, client: VillageACPClient):
        """Test read_text_file is denied by default."""
        with pytest.raises(PermissionError, match="File reads not allowed"):
            await client.read_text_file(
                path="/tmp/test.txt",
                session_id="test-session",
            )

    async def test_read_text_file_with_limit(self, client: VillageACPClient):
        """Test read_text_file rejects even with limit."""
        with pytest.raises(PermissionError):
            await client.read_text_file(
                path="/tmp/test.txt",
                session_id="test-session",
                limit=100,
            )

    async def test_read_text_file_with_line(self, client: VillageACPClient):
        """Test read_text_file rejects even with line param."""
        with pytest.raises(PermissionError):
            await client.read_text_file(
                path="/tmp/test.txt",
                session_id="test-session",
                line=10,
            )


@pytest.mark.asyncio
class TestCreateTerminal:
    """Test create_terminal method."""

    async def test_create_terminal_denied(self, client: VillageACPClient):
        """Test create_terminal is denied by default."""
        with pytest.raises(PermissionError, match="Terminal creation not allowed"):
            await client.create_terminal(
                command="echo test",
                session_id="test-session",
            )

    async def test_create_terminal_with_args(self, client: VillageACPClient):
        """Test create_terminal rejects even with args."""
        with pytest.raises(PermissionError):
            await client.create_terminal(
                command="echo",
                session_id="test-session",
                args=["test"],
            )

    async def test_create_terminal_with_cwd(self, client: VillageACPClient):
        """Test create_terminal rejects even with cwd."""
        with pytest.raises(PermissionError):
            await client.create_terminal(
                command="echo test",
                session_id="test-session",
                cwd="/tmp",
            )

    async def test_create_terminal_with_env(self, client: VillageACPClient):
        """Test create_terminal rejects even with env."""
        with pytest.raises(PermissionError):
            await client.create_terminal(
                command="echo test",
                session_id="test-session",
                env=[{"name": "TEST", "value": "value"}],
            )

    async def test_create_terminal_with_output_limit(self, client: VillageACPClient):
        """Test create_terminal rejects even with output limit."""
        with pytest.raises(PermissionError):
            await client.create_terminal(
                command="echo test",
                session_id="test-session",
                output_byte_limit=1000,
            )


@pytest.mark.asyncio
class TestTerminalOutput:
    """Test terminal_output method."""

    async def test_terminal_output_denied(self, client: VillageACPClient):
        """Test terminal_output is denied by default."""
        with pytest.raises(PermissionError, match="Terminal access not allowed"):
            await client.terminal_output(
                session_id="test-session",
                terminal_id="term-123",
            )

    async def test_terminal_output_with_kwargs(self, client: VillageACPClient):
        """Test terminal_output rejects even with kwargs."""
        with pytest.raises(PermissionError):
            await client.terminal_output(
                session_id="test-session",
                terminal_id="term-123",
                extra_param="ignored",
            )


@pytest.mark.asyncio
class TestReleaseTerminal:
    """Test release_terminal method."""

    async def test_release_terminal_denied(self, client: VillageACPClient):
        """Test release_terminal is denied by default."""
        with pytest.raises(PermissionError, match="Terminal operations not allowed"):
            await client.release_terminal(
                session_id="test-session",
                terminal_id="term-123",
            )

    async def test_release_terminal_with_kwargs(self, client: VillageACPClient):
        """Test release_terminal rejects even with kwargs."""
        with pytest.raises(PermissionError):
            await client.release_terminal(
                session_id="test-session",
                terminal_id="term-123",
                extra_param="ignored",
            )


@pytest.mark.asyncio
class TestWaitForTerminalExit:
    """Test wait_for_terminal_exit method."""

    async def test_wait_for_terminal_exit_denied(self, client: VillageACPClient):
        """Test wait_for_terminal_exit is denied by default."""
        with pytest.raises(PermissionError, match="Terminal operations not allowed"):
            await client.wait_for_terminal_exit(
                session_id="test-session",
                terminal_id="term-123",
            )

    async def test_wait_for_terminal_exit_with_kwargs(self, client: VillageACPClient):
        """Test wait_for_terminal_exit rejects even with kwargs."""
        with pytest.raises(PermissionError):
            await client.wait_for_terminal_exit(
                session_id="test-session",
                terminal_id="term-123",
                extra_param="ignored",
            )


@pytest.mark.asyncio
class TestKillTerminal:
    """Test kill_terminal method."""

    async def test_kill_terminal_denied(self, client: VillageACPClient):
        """Test kill_terminal is denied by default."""
        with pytest.raises(PermissionError, match="Terminal operations not allowed"):
            await client.kill_terminal(
                session_id="test-session",
                terminal_id="term-123",
            )

    async def test_kill_terminal_with_kwargs(self, client: VillageACPClient):
        """Test kill_terminal rejects even with kwargs."""
        with pytest.raises(PermissionError):
            await client.kill_terminal(
                session_id="test-session",
                terminal_id="term-123",
                extra_param="ignored",
            )


@pytest.mark.asyncio
class TestExtMethods:
    """Test extension methods."""

    async def test_ext_method_returns_empty_dict(self, client: VillageACPClient):
        """Test ext_method returns empty dict for unknown methods."""
        result = await client.ext_method(
            method="unknown/method",
            params={},
        )

        assert result == {}

    async def test_ext_notification_no_error(self, client: VillageACPClient):
        """Test ext_notification handles unknown notifications."""
        await client.ext_notification(
            method="unknown/notification",
            params={},
        )


@pytest.mark.asyncio
class TestOnConnect:
    """Test on_connect method."""

    async def test_on_connect_no_error(self, client: VillageACPClient):
        """Test on_connect handles agent connection."""
        mock_conn = MagicMock()

        client.on_connect(mock_conn)


@pytest.mark.asyncio
class TestSpawnACPAgent:
    """Test spawn_acp_agent function."""

    async def test_spawn_acp_agent_creates_client(self):
        """Test spawn_acp_agent creates VillageACPClient."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            await spawn_acp_agent("echo test")

            mock_spawn.assert_called_once()
            client_arg = mock_spawn.call_args[0][0]
            assert isinstance(client_arg, VillageACPClient)

    async def test_spawn_acp_agent_parses_command(self):
        """Test spawn_acp_agent parses command string."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            await spawn_acp_agent("claude-code --model claude-3")

            call_args = mock_spawn.call_args
            assert call_args[0][1] == "claude-code"
            assert call_args[0][2] == "--model"
            assert call_args[0][3] == "claude-3"

    async def test_spawn_acp_agent_with_cwd(self, tmp_path: Path):
        """Test spawn_acp_agent passes cwd."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            await spawn_acp_agent("echo test", cwd=tmp_path)

            call_kwargs = mock_spawn.call_args[1]
            assert call_kwargs["cwd"] == str(tmp_path)

    async def test_spawn_acp_agent_returns_connection_and_process(self):
        """Test spawn_acp_agent returns connection and process."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_conn = MagicMock()
            mock_proc = MagicMock()

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(mock_conn, mock_proc))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            conn, proc = await spawn_acp_agent("echo test")

            assert conn == mock_conn
            assert proc == mock_proc


@pytest.mark.asyncio
class TestTestACPAgent:
    """Test test_acp_agent function."""

    async def test_test_acp_agent_success(self):
        """Test test_acp_agent returns True on success."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_conn = MagicMock()
            mock_conn.initialize = AsyncMock(return_value={})
            mock_conn.new_session = AsyncMock(return_value=MagicMock(session_id="test"))
            mock_conn.prompt = AsyncMock(return_value={})

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(mock_conn, MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            result = await test_acp_agent("echo test")

            assert result is True

    async def test_test_acp_agent_failure(self):
        """Test test_acp_agent returns False on failure."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            result = await test_acp_agent("invalid-command")

            assert result is False

    async def test_test_acp_agent_parses_command(self):
        """Test test_acp_agent parses command string."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_conn = MagicMock()
            mock_conn.initialize = AsyncMock(return_value={})
            mock_conn.new_session = AsyncMock(return_value=MagicMock(session_id="test"))
            mock_conn.prompt = AsyncMock(return_value={})

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(mock_conn, MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            await test_acp_agent("claude-code --model claude-3")

            call_args = mock_spawn.call_args
            assert call_args[0][1] == "claude-code"
            assert call_args[0][2] == "--model"
            assert call_args[0][3] == "claude-3"

    async def test_test_acp_agent_sends_test_prompt(self):
        """Test test_acp_agent sends test prompt."""
        with patch("village.acp.external_client.spawn_agent_process") as mock_spawn:
            mock_conn = MagicMock()
            mock_conn.initialize = AsyncMock(return_value={})
            mock_conn.new_session = AsyncMock(return_value=MagicMock(session_id="test-session"))
            mock_conn.prompt = AsyncMock(return_value={})

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=(mock_conn, MagicMock()))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            await test_acp_agent("echo test")

            mock_conn.prompt.assert_called_once()
            prompt_arg = mock_conn.prompt.call_args[1]["prompt"]
            assert len(prompt_arg) > 0


@pytest.mark.asyncio
class TestClientSecurityModel:
    """Test VillageACPClient security model."""

    async def test_all_file_operations_denied(self, client: VillageACPClient):
        """Test all file operations are denied."""
        with pytest.raises(PermissionError):
            await client.read_text_file(
                path="/tmp/test.txt",
                session_id="test",
            )

        with pytest.raises(PermissionError):
            await client.write_text_file(
                path="/tmp/test.txt",
                content="test",
                session_id="test",
            )

    async def test_all_terminal_operations_denied(self, client: VillageACPClient):
        """Test all terminal operations are denied."""
        with pytest.raises(PermissionError):
            await client.create_terminal(
                command="test",
                session_id="test",
            )

        with pytest.raises(PermissionError):
            await client.terminal_output(
                session_id="test",
                terminal_id="term-1",
            )

        with pytest.raises(PermissionError):
            await client.release_terminal(
                session_id="test",
                terminal_id="term-1",
            )

        with pytest.raises(PermissionError):
            await client.wait_for_terminal_exit(
                session_id="test",
                terminal_id="term-1",
            )

        with pytest.raises(PermissionError):
            await client.kill_terminal(
                session_id="test",
                terminal_id="term-1",
            )

    async def test_only_permission_and_update_allowed(self, client: VillageACPClient):
        """Test only permission and update methods are allowed."""
        result = await client.request_permission(
            options={},
            session_id="test",
            tool_call={},
        )
        assert result is not None

        await client.session_update(
            session_id="test",
            update={},
        )
