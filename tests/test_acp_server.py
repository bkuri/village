"""Tests for VillageACPAgent - ACP Agent implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from village.acp.agent import VillageACPAgent, run_village_agent
from village.config import Config


@pytest.fixture
def agent(acp_config: Config):
    """Create VillageACPAgent with test config."""
    return VillageACPAgent(acp_config)


@pytest.mark.asyncio
class TestVillageACPAgentInit:
    """Test VillageACPAgent initialization."""

    async def test_agent_creates_bridge(self, acp_config: Config):
        """Test agent creates ACPBridge on init."""
        agent = VillageACPAgent(acp_config)
        assert agent.bridge is not None
        assert agent.config == acp_config

    async def test_agent_uses_default_config(self):
        """Test agent uses default config when none provided."""
        with patch("village.acp.agent.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            agent = VillageACPAgent()
            assert agent.config == mock_config


@pytest.mark.asyncio
class TestInitialize:
    """Test ACP initialize method."""

    async def test_initialize_returns_protocol_version(self, agent: VillageACPAgent):
        """Test initialize returns correct protocol version."""
        result = await agent.initialize(protocol_version=1)

        assert result.protocol_version == 1

    async def test_initialize_returns_capabilities(self, agent: VillageACPAgent):
        """Test initialize returns agent capabilities."""
        result = await agent.initialize(protocol_version=1)

        assert result.agent_capabilities is not None

    async def test_initialize_returns_agent_info(self, agent: VillageACPAgent):
        """Test initialize returns agent info."""
        result = await agent.initialize(protocol_version=1)

        assert result.agent_info.name == "village"
        assert result.agent_info.version == "1.0.0"

    async def test_initialize_with_client_capabilities(self, agent: VillageACPAgent):
        """Test initialize accepts client capabilities."""
        from acp.schema import ClientCapabilities, Implementation

        client_caps = ClientCapabilities()
        client_info = Implementation(name="test-client", version="1.0.0")

        result = await agent.initialize(
            protocol_version=1,
            client_capabilities=client_caps,
            client_info=client_info,
        )

        assert result is not None

    async def test_initialize_with_kwargs(self, agent: VillageACPAgent):
        """Test initialize accepts additional kwargs."""
        result = await agent.initialize(protocol_version=1, extra_param="ignored")

        assert result is not None


@pytest.mark.asyncio
class TestNewSession:
    """Test ACP new_session method."""

    async def test_new_session_creates_session(self, agent: VillageACPAgent):
        """Test new_session creates ACP session."""
        result = await agent.new_session(
            cwd="/tmp/test",
            sessionId="test-session-1",
        )

        assert result.session_id == "test-session-1"

    async def test_new_session_calls_bridge(self, agent: VillageACPAgent):
        """Test new_session calls bridge.session_new."""
        with patch.object(agent.bridge, "session_new", new_callable=AsyncMock) as mock_new:
            mock_new.return_value = {"sessionId": "test-session-2", "state": "queued"}

            result = await agent.new_session(
                cwd="/tmp/test",
                sessionId="test-session-2",
            )

            mock_new.assert_called_once()
            assert result.session_id == "test-session-2"

    async def test_new_session_with_mcp_servers(self, agent: VillageACPAgent):
        """Test new_session accepts MCP servers."""
        result = await agent.new_session(
            cwd="/tmp/test",
            sessionId="test-session-3",
            mcp_servers=[],
        )

        assert result is not None

    async def test_new_session_with_kwargs(self, agent: VillageACPAgent):
        """Test new_session accepts additional kwargs."""
        result = await agent.new_session(
            cwd="/tmp/test",
            sessionId="test-session-4",
            extra_param="ignored",
        )

        assert result is not None


@pytest.mark.asyncio
class TestLoadSession:
    """Test ACP load_session method."""

    async def test_load_session_loads_existing(self, agent: VillageACPAgent):
        """Test load_session loads existing session."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-load-1")

        result = await agent.load_session(
            cwd="/tmp/test",
            session_id="test-load-1",
        )

        assert result is not None

    async def test_load_session_calls_bridge(self, agent: VillageACPAgent):
        """Test load_session calls bridge.session_load."""
        with patch.object(agent.bridge, "session_load", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = {"sessionId": "test-load-2", "state": "queued"}

            result = await agent.load_session(
                cwd="/tmp/test",
                session_id="test-load-2",
            )

            mock_load.assert_called_once_with({"sessionId": "test-load-2"})

    async def test_load_session_with_mcp_servers(self, agent: VillageACPAgent):
        """Test load_session accepts MCP servers."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-load-3")

        result = await agent.load_session(
            cwd="/tmp/test",
            session_id="test-load-3",
            mcp_servers=[],
        )

        assert result is not None


@pytest.mark.asyncio
class TestListSessions:
    """Test ACP list_sessions method."""

    async def test_list_sessions_returns_list(self, agent: VillageACPAgent):
        """Test list_sessions returns list."""
        result = await agent.list_sessions()

        assert result.sessions == []

    async def test_list_sessions_with_cursor(self, agent: VillageACPAgent):
        """Test list_sessions accepts cursor."""
        result = await agent.list_sessions(cursor="cursor-123")

        assert result is not None

    async def test_list_sessions_with_cwd(self, agent: VillageACPAgent):
        """Test list_sessions accepts cwd."""
        result = await agent.list_sessions(cwd="/tmp/test")

        assert result is not None


@pytest.mark.asyncio
class TestSetSessionMode:
    """Test ACP set_session_mode method."""

    async def test_set_session_mode_returns_none(self, agent: VillageACPAgent):
        """Test set_session_mode returns None (not implemented)."""
        result = await agent.set_session_mode(
            mode_id="default",
            session_id="test-session",
        )

        assert result is None


@pytest.mark.asyncio
class TestSetSessionModel:
    """Test ACP set_session_model method."""

    async def test_set_session_model_returns_none(self, agent: VillageACPAgent):
        """Test set_session_model returns None (not implemented)."""
        result = await agent.set_session_model(
            model_id="claude-3",
            session_id="test-session",
        )

        assert result is None


@pytest.mark.asyncio
class TestSetConfigOption:
    """Test ACP set_config_option method."""

    async def test_set_config_option_returns_none(self, agent: VillageACPAgent):
        """Test set_config_option returns None (not implemented)."""
        result = await agent.set_config_option(
            config_id="test-option",
            session_id="test-session",
            value="test-value",
        )

        assert result is None


@pytest.mark.asyncio
class TestAuthenticate:
    """Test ACP authenticate method."""

    async def test_authenticate_returns_none(self, agent: VillageACPAgent):
        """Test authenticate returns None (not required)."""
        result = await agent.authenticate(method_id="none")

        assert result is None


@pytest.mark.asyncio
class TestPrompt:
    """Test ACP prompt method."""

    async def test_prompt_with_text_blocks(self, agent: VillageACPAgent):
        """Test prompt with text blocks."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-prompt-1")

        with patch.object(agent.bridge, "session_prompt", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = (
                {"sessionId": "test-prompt-1", "stopReason": "end_turn"},
                [],
            )

            result = await agent.prompt(
                prompt=[{"text": "Hello, Village!"}],
                session_id="test-prompt-1",
            )

            assert result.stop_reason == "end_turn"
            mock_prompt.assert_called_once()

    async def test_prompt_extracts_text(self, agent: VillageACPAgent):
        """Test prompt extracts text from blocks."""
        text = agent._extract_text([{"text": "Hello"}, {"text": "World"}])

        assert text == "Hello World"

    async def test_prompt_with_object_blocks(self, agent: VillageACPAgent):
        """Test prompt with object-style text blocks."""
        mock_block = MagicMock()
        mock_block.text = "Test message"

        text = agent._extract_text([mock_block])

        assert text == "Test message"

    async def test_prompt_with_agent_param(self, agent: VillageACPAgent):
        """Test prompt uses agent parameter."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-prompt-2")

        with patch.object(agent.bridge, "session_prompt", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = (
                {"sessionId": "test-prompt-2", "stopReason": "end_turn"},
                [],
            )

            await agent.prompt(
                prompt=[{"text": "Test"}],
                session_id="test-prompt-2",
                agent="custom-agent",
            )

            call_args = mock_prompt.call_args[0][0]
            assert call_args["agent"] == "custom-agent"

    async def test_prompt_uses_default_agent(self, agent: VillageACPAgent):
        """Test prompt uses default agent from config."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-prompt-3")

        with patch.object(agent.bridge, "session_prompt", new_callable=AsyncMock) as mock_prompt:
            mock_prompt.return_value = (
                {"sessionId": "test-prompt-3", "stopReason": "end_turn"},
                [],
            )

            await agent.prompt(
                prompt=[{"text": "Test"}],
                session_id="test-prompt-3",
            )

            call_args = mock_prompt.call_args[0][0]
            assert "agent" in call_args


@pytest.mark.asyncio
class TestForkSession:
    """Test ACP fork_session method."""

    async def test_fork_session_raises_not_implemented(self, agent: VillageACPAgent):
        """Test fork_session raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Session forking not supported"):
            await agent.fork_session(
                cwd="/tmp/test",
                session_id="test-session",
            )


@pytest.mark.asyncio
class TestResumeSession:
    """Test ACP resume_session method."""

    async def test_resume_session_loads_session(self, agent: VillageACPAgent):
        """Test resume_session loads existing session."""
        await agent.new_session(cwd="/tmp/test", sessionId="test-resume-1")

        with patch.object(agent.bridge, "session_load", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = {"sessionId": "test-resume-1", "state": "paused"}

            result = await agent.resume_session(
                cwd="/tmp/test",
                session_id="test-resume-1",
            )

            mock_load.assert_called_once()
            assert result is not None


@pytest.mark.asyncio
class TestCancel:
    """Test ACP cancel method."""

    async def test_cancel_calls_bridge(self, agent: VillageACPAgent):
        """Test cancel calls bridge.session_cancel."""
        with patch.object(agent.bridge, "session_cancel", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = {"sessionId": "test-cancel-1", "state": "cancelled"}

            await agent.cancel(session_id="test-cancel-1")

            mock_cancel.assert_called_once_with({"sessionId": "test-cancel-1"})

    async def test_cancel_with_kwargs(self, agent: VillageACPAgent):
        """Test cancel accepts additional kwargs."""
        with patch.object(agent.bridge, "session_cancel", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = {"sessionId": "test-cancel-2", "state": "cancelled"}

            await agent.cancel(session_id="test-cancel-2", extra_param="ignored")

            mock_cancel.assert_called_once()


@pytest.mark.asyncio
class TestExtMethods:
    """Test ACP extension methods."""

    async def test_ext_method_returns_empty_dict(self, agent: VillageACPAgent):
        """Test ext_method returns empty dict for unknown methods."""
        result = await agent.ext_method(
            method="unknown/method",
            params={},
        )

        assert result == {}

    async def test_ext_notification_no_error(self, agent: VillageACPAgent):
        """Test ext_notification handles unknown notifications."""
        await agent.ext_notification(
            method="unknown/notification",
            params={},
        )


@pytest.mark.asyncio
class TestOnConnect:
    """Test ACP on_connect method."""

    async def test_on_connect_no_error(self, agent: VillageACPAgent):
        """Test on_connect handles client connection."""
        mock_conn = MagicMock()

        agent.on_connect(mock_conn)


@pytest.mark.asyncio
class TestExtractText:
    """Test _extract_text helper method."""

    async def test_extract_text_from_dict_blocks(self, agent: VillageACPAgent):
        """Test extracting text from dict-style blocks."""
        blocks = [
            {"text": "First"},
            {"text": "Second"},
            {"text": "Third"},
        ]

        text = agent._extract_text(blocks)

        assert text == "First Second Third"

    async def test_extract_text_from_object_blocks(self, agent: VillageACPAgent):
        """Test extracting text from object-style blocks."""
        blocks = [
            MagicMock(text="Block1"),
            MagicMock(text="Block2"),
        ]

        text = agent._extract_text(blocks)

        assert text == "Block1 Block2"

    async def test_extract_text_mixed_blocks(self, agent: VillageACPAgent):
        """Test extracting text from mixed block types."""
        blocks = [
            {"text": "Dict"},
            MagicMock(text="Object"),
        ]

        text = agent._extract_text(blocks)

        assert text == "Dict Object"

    async def test_extract_text_empty_list(self, agent: VillageACPAgent):
        """Test extracting text from empty list."""
        text = agent._extract_text([])

        assert text == ""

    async def test_extract_text_ignores_non_text_blocks(self, agent: VillageACPAgent):
        """Test extracting text ignores blocks without text."""
        blocks = [
            {"type": "image", "url": "http://example.com/img.png"},
            {"text": "Text block"},
        ]

        text = agent._extract_text(blocks)

        assert text == "Text block"


@pytest.mark.asyncio
class TestRunVillageAgent:
    """Test run_village_agent function."""

    async def test_run_village_agent_creates_agent(self, acp_config: Config):
        """Test run_village_agent creates VillageACPAgent."""
        with patch("village.acp.agent.run_agent") as mock_run:
            await run_village_agent(acp_config)

            mock_run.assert_called_once()
            agent_arg = mock_run.call_args[0][0]
            assert isinstance(agent_arg, VillageACPAgent)

    async def test_run_village_agent_uses_config(self, acp_config: Config):
        """Test run_village_agent uses provided config."""
        with patch("village.acp.agent.run_agent") as mock_run:
            await run_village_agent(acp_config)

            agent_arg = mock_run.call_args[0][0]
            assert agent_arg.config == acp_config

    async def test_run_village_agent_default_config(self):
        """Test run_village_agent uses default config if not provided."""
        with patch("village.acp.agent.run_agent") as mock_run:
            with patch("village.acp.agent.get_config") as mock_get_config:
                mock_config = MagicMock()
                mock_get_config.return_value = mock_config

                await run_village_agent()

                mock_get_config.assert_called_once()
