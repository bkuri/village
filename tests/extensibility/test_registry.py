"""Tests for ExtensionRegistry class."""

from unittest.mock import MagicMock, patch

import pytest

from village.extensibility.beads_integrators import (
    BeadsIntegrator,
    BeadSpec,
    DefaultBeadsIntegrator,
)
from village.extensibility.context import ChatContext, DefaultChatContext, SessionContext
from village.extensibility.llm_adapters import (
    DefaultLLMProviderAdapter,
    LLMProviderAdapter,
    LLMProviderConfig,
)
from village.extensibility.processors import ChatProcessor, DefaultChatProcessor
from village.extensibility.registry import ExtensionRegistry
from village.extensibility.server_discovery import (
    DefaultServerDiscovery,
    MCPServer,
    ServerDiscovery,
)
from village.extensibility.thinking_refiners import (
    DefaultThinkingRefiner,
    QueryRefinement,
    ThinkingRefiner,
)
from village.extensibility.tool_invokers import (
    DefaultToolInvoker,
    ToolInvocation,
    ToolInvoker,
)


class MockChatProcessor(ChatProcessor):
    """Mock chat processor for testing."""

    async def pre_process(self, user_input: str) -> str:
        return f"MOCK_PRE: {user_input}"

    async def post_process(self, response: str) -> str:
        return f"MOCK_POST: {response}"


class MockToolInvoker(ToolInvoker):
    """Mock tool invoker for testing."""

    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
        return {"mock": True, **invocation.args}

    async def on_success(self, invocation: ToolInvocation, result: object) -> object:
        return {"mock_success": True, "result": result}

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        pass


class MockThinkingRefiner(ThinkingRefiner):
    """Mock thinking refiner for testing."""

    async def should_refine(self, user_query: str) -> bool:
        return "refine" in user_query.lower()

    async def refine_query(self, user_query: str) -> QueryRefinement:
        return QueryRefinement(
            original_query=user_query,
            refined_steps=[f"Mock step 1: {user_query}", "Mock step 2: analyze"],
        )


class MockChatContext(ChatContext):
    """Mock chat context for testing."""

    async def load_context(self, session_id: str) -> SessionContext:
        return SessionContext(
            session_id=session_id,
            user_data={"mock_data": f"session_{session_id}"},
        )

    async def save_context(self, context: SessionContext) -> None:
        context.metadata["saved"] = True

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        context.metadata["enriched"] = True
        return context


class MockBeadsIntegrator(BeadsIntegrator):
    """Mock beads integrator for testing."""

    async def should_create_bead(self, context: dict[str, object]) -> bool:
        return bool(context.get("create_bead", False))

    async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
        title = context.get("title", "Mock Bead")
        description = context.get("description", "Mock description")
        assert isinstance(title, str)
        assert isinstance(description, str)
        return BeadSpec(
            title=title,
            description=description,
            issue_type="task",
            priority=1,
        )

    async def on_bead_created(self, bead: object, context: dict[str, object]) -> None:
        context["created"] = True

    async def on_bead_updated(self, bead_id: str, updates: dict[str, object]) -> None:
        pass


class MockServerDiscovery(ServerDiscovery):
    """Mock server discovery for testing."""

    async def discover_servers(self) -> list[MCPServer]:
        return [
            MCPServer(
                name="mock-server-1",
                type="stdio",
                command="mock-command",
            ),
            MCPServer(
                name="mock-server-2",
                type="sse",
                command="mock-sse-command",
            ),
        ]

    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        return [s for s in servers if "1" not in s.name]

    async def should_load_server(self, server: MCPServer) -> bool:
        return server.enabled and "2" in server.name


class MockLLMAdapter(LLMProviderAdapter):
    """Mock LLM adapter for testing."""

    async def adapt_config(self, base_config: LLMProviderConfig) -> LLMProviderConfig:
        return LLMProviderConfig(
            provider="mock-provider",
            model="mock-model",
            api_key_env="MOCK_API_KEY",
            timeout=60,
            max_tokens=1024,
            temperature=0.5,
        )

    async def should_retry(self, error: Exception) -> bool:
        return "retryable" in str(error).lower()

    async def get_retry_delay(self, attempt: int) -> float:
        return float(attempt * 2.0)


class TestExtensionRegistryInitialization:
    """Tests for ExtensionRegistry initialization."""

    def test_registry_initializes_with_all_default_implementations(
        self,
    ) -> None:
        """Registry initializes with all default implementations."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_processor(), DefaultChatProcessor)
        assert isinstance(registry.get_tool_invoker(), DefaultToolInvoker)
        assert isinstance(registry.get_thinking_refiner(), DefaultThinkingRefiner)
        assert isinstance(registry.get_chat_context(), DefaultChatContext)
        assert isinstance(registry.get_beads_integrator(), DefaultBeadsIntegrator)
        assert isinstance(registry.get_server_discovery(), DefaultServerDiscovery)
        assert isinstance(registry.get_llm_adapter(), DefaultLLMProviderAdapter)

    def test_get_all_names_returns_correct_default_class_names(
        self,
    ) -> None:
        """get_all_names() returns correct class names for defaults."""
        registry = ExtensionRegistry()
        names = registry.get_all_names()

        assert names == {
            "processor": "DefaultChatProcessor",
            "tool_invoker": "DefaultToolInvoker",
            "thinking_refiner": "DefaultThinkingRefiner",
            "chat_context": "DefaultChatContext",
            "beads_integrator": "DefaultBeadsIntegrator",
            "server_discovery": "DefaultServerDiscovery",
            "llm_adapter": "DefaultLLMProviderAdapter",
        }

    def test_multiple_registries_have_independent_state(self) -> None:
        """Multiple registries maintain independent state."""
        registry1 = ExtensionRegistry()
        registry2 = ExtensionRegistry()

        mock_processor = MockChatProcessor()
        registry1.register_processor(mock_processor)

        assert isinstance(registry1.get_processor(), MockChatProcessor)
        assert isinstance(registry2.get_processor(), DefaultChatProcessor)


class TestExtensionRegistryRegistration:
    """Tests for ExtensionRegistry registration methods."""

    def test_register_processor_replaces_default_with_custom(
        self,
    ) -> None:
        """register_processor() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_processor = MockChatProcessor()

        registry.register_processor(mock_processor)

        assert registry.get_processor() is mock_processor
        assert isinstance(registry.get_processor(), MockChatProcessor)

    def test_register_tool_invoker_replaces_default_with_custom(
        self,
    ) -> None:
        """register_tool_invoker() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_invoker = MockToolInvoker()

        registry.register_tool_invoker(mock_invoker)

        assert registry.get_tool_invoker() is mock_invoker
        assert isinstance(registry.get_tool_invoker(), MockToolInvoker)

    def test_register_thinking_refiner_replaces_default_with_custom(
        self,
    ) -> None:
        """register_thinking_refiner() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_refiner = MockThinkingRefiner()

        registry.register_thinking_refiner(mock_refiner)

        assert registry.get_thinking_refiner() is mock_refiner
        assert isinstance(registry.get_thinking_refiner(), MockThinkingRefiner)

    def test_register_chat_context_replaces_default_with_custom(
        self,
    ) -> None:
        """register_chat_context() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_context = MockChatContext()

        registry.register_chat_context(mock_context)

        assert registry.get_chat_context() is mock_context
        assert isinstance(registry.get_chat_context(), MockChatContext)

    def test_register_beads_integrator_replaces_default_with_custom(
        self,
    ) -> None:
        """register_beads_integrator() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_integrator = MockBeadsIntegrator()

        registry.register_beads_integrator(mock_integrator)

        assert registry.get_beads_integrator() is mock_integrator
        assert isinstance(registry.get_beads_integrator(), MockBeadsIntegrator)

    def test_register_server_discovery_replaces_default_with_custom(
        self,
    ) -> None:
        """register_server_discovery() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_discovery = MockServerDiscovery()

        registry.register_server_discovery(mock_discovery)

        assert registry.get_server_discovery() is mock_discovery
        assert isinstance(registry.get_server_discovery(), MockServerDiscovery)

    def test_register_llm_adapter_replaces_default_with_custom(
        self,
    ) -> None:
        """register_llm_adapter() replaces default with custom."""
        registry = ExtensionRegistry()
        mock_adapter = MockLLMAdapter()

        registry.register_llm_adapter(mock_adapter)

        assert registry.get_llm_adapter() is mock_adapter
        assert isinstance(registry.get_llm_adapter(), MockLLMAdapter)

    def test_register_processor_replaces_existing_custom(self) -> None:
        """register_processor() replaces existing custom implementation."""
        registry = ExtensionRegistry()
        mock1 = MockChatProcessor()
        mock2 = MockChatProcessor()

        registry.register_processor(mock1)
        assert registry.get_processor() is mock1

        registry.register_processor(mock2)
        assert registry.get_processor() is mock2


class TestExtensionRegistryGetters:
    """Tests for ExtensionRegistry getter methods."""

    def test_get_processor_returns_registered_or_default(self) -> None:
        """get_processor() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_processor(), DefaultChatProcessor)

        mock_processor = MockChatProcessor()
        registry.register_processor(mock_processor)
        assert registry.get_processor() is mock_processor

    def test_get_tool_invoker_returns_registered_or_default(self) -> None:
        """get_tool_invoker() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_tool_invoker(), DefaultToolInvoker)

        mock_invoker = MockToolInvoker()
        registry.register_tool_invoker(mock_invoker)
        assert registry.get_tool_invoker() is mock_invoker

    def test_get_thinking_refiner_returns_registered_or_default(
        self,
    ) -> None:
        """get_thinking_refiner() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_thinking_refiner(), DefaultThinkingRefiner)

        mock_refiner = MockThinkingRefiner()
        registry.register_thinking_refiner(mock_refiner)
        assert registry.get_thinking_refiner() is mock_refiner

    def test_get_chat_context_returns_registered_or_default(
        self,
    ) -> None:
        """get_chat_context() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_chat_context(), DefaultChatContext)

        mock_context = MockChatContext()
        registry.register_chat_context(mock_context)
        assert registry.get_chat_context() is mock_context

    def test_get_beads_integrator_returns_registered_or_default(
        self,
    ) -> None:
        """get_beads_integrator() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_beads_integrator(), DefaultBeadsIntegrator)

        mock_integrator = MockBeadsIntegrator()
        registry.register_beads_integrator(mock_integrator)
        assert registry.get_beads_integrator() is mock_integrator

    def test_get_server_discovery_returns_registered_or_default(
        self,
    ) -> None:
        """get_server_discovery() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_server_discovery(), DefaultServerDiscovery)

        mock_discovery = MockServerDiscovery()
        registry.register_server_discovery(mock_discovery)
        assert registry.get_server_discovery() is mock_discovery

    def test_get_llm_adapter_returns_registered_or_default(self) -> None:
        """get_llm_adapter() returns registered or default."""
        registry = ExtensionRegistry()

        assert isinstance(registry.get_llm_adapter(), DefaultLLMProviderAdapter)

        mock_adapter = MockLLMAdapter()
        registry.register_llm_adapter(mock_adapter)
        assert registry.get_llm_adapter() is mock_adapter

    def test_get_all_names_reflects_current_registrations(
        self,
    ) -> None:
        """get_all_names() reflects current registrations."""
        registry = ExtensionRegistry()
        mock_processor = MockChatProcessor()
        mock_invoker = MockToolInvoker()

        registry.register_processor(mock_processor)
        registry.register_tool_invoker(mock_invoker)

        names = registry.get_all_names()
        assert names["processor"] == "MockChatProcessor"
        assert names["tool_invoker"] == "MockToolInvoker"
        assert names["thinking_refiner"] == "DefaultThinkingRefiner"


class TestExtensionRegistryReset:
    """Tests for ExtensionRegistry reset functionality."""

    def test_reset_to_defaults_resets_all_extensions(self) -> None:
        """reset_to_defaults() resets all extensions to defaults."""
        registry = ExtensionRegistry()

        registry.register_processor(MockChatProcessor())
        registry.register_tool_invoker(MockToolInvoker())
        registry.register_thinking_refiner(MockThinkingRefiner())
        registry.register_chat_context(MockChatContext())
        registry.register_beads_integrator(MockBeadsIntegrator())
        registry.register_server_discovery(MockServerDiscovery())
        registry.register_llm_adapter(MockLLMAdapter())

        registry.reset_to_defaults()

        assert isinstance(registry.get_processor(), DefaultChatProcessor)
        assert isinstance(registry.get_tool_invoker(), DefaultToolInvoker)
        assert isinstance(registry.get_thinking_refiner(), DefaultThinkingRefiner)
        assert isinstance(registry.get_chat_context(), DefaultChatContext)
        assert isinstance(registry.get_beads_integrator(), DefaultBeadsIntegrator)
        assert isinstance(registry.get_server_discovery(), DefaultServerDiscovery)
        assert isinstance(registry.get_llm_adapter(), DefaultLLMProviderAdapter)

    def test_reset_to_defaults_when_already_default_is_no_op(
        self,
    ) -> None:
        """reset_to_defaults() when already default is no-op."""
        registry = ExtensionRegistry()
        names_before = registry.get_all_names()

        registry.reset_to_defaults()
        names_after = registry.get_all_names()

        assert names_before == names_after


class TestExtensionRegistryIntegrationWithMocks:
    """Integration tests with mock extensions."""

    def test_verify_mock_processor_registered_and_retrieved(
        self,
    ) -> None:
        """Verify mock ChatProcessor is registered and retrieved correctly."""
        registry = ExtensionRegistry()
        mock_processor = MockChatProcessor()

        registry.register_processor(mock_processor)
        retrieved = registry.get_processor()

        assert retrieved is mock_processor
        assert isinstance(retrieved, MockChatProcessor)

    def test_verify_mock_tool_invoker_registered_and_retrieved(
        self,
    ) -> None:
        """Verify mock ToolInvoker is registered and retrieved correctly."""
        registry = ExtensionRegistry()
        mock_invoker = MockToolInvoker()

        registry.register_tool_invoker(mock_invoker)
        retrieved = registry.get_tool_invoker()

        assert retrieved is mock_invoker
        assert isinstance(retrieved, MockToolInvoker)

    def test_verify_all_extensions_can_be_replaced_simultaneously(
        self,
    ) -> None:
        """Verify all extensions can be replaced simultaneously."""
        registry = ExtensionRegistry()

        registry.register_processor(MockChatProcessor())
        registry.register_tool_invoker(MockToolInvoker())
        registry.register_thinking_refiner(MockThinkingRefiner())
        registry.register_chat_context(MockChatContext())
        registry.register_beads_integrator(MockBeadsIntegrator())
        registry.register_server_discovery(MockServerDiscovery())
        registry.register_llm_adapter(MockLLMAdapter())

        names = registry.get_all_names()
        assert all("Mock" in name for name in names.values())

        assert isinstance(registry.get_processor(), MockChatProcessor)
        assert isinstance(registry.get_tool_invoker(), MockToolInvoker)
        assert isinstance(registry.get_thinking_refiner(), MockThinkingRefiner)
        assert isinstance(registry.get_chat_context(), MockChatContext)
        assert isinstance(registry.get_beads_integrator(), MockBeadsIntegrator)
        assert isinstance(registry.get_server_discovery(), MockServerDiscovery)
        assert isinstance(registry.get_llm_adapter(), MockLLMAdapter)

    def test_verify_names_update_after_replacement(self) -> None:
        """Verify get_all_names updates after replacement."""
        registry = ExtensionRegistry()

        names_initial = registry.get_all_names()
        assert "Default" in names_initial["processor"]

        registry.register_processor(MockChatProcessor())
        registry.register_llm_adapter(MockLLMAdapter())

        names_after = registry.get_all_names()
        assert names_after["processor"] == "MockChatProcessor"
        assert names_after["llm_adapter"] == "MockLLMAdapter"
        assert "Default" in names_after["tool_invoker"]


class TestExtensionRegistryLogging:
    """Tests for ExtensionRegistry logging behavior."""

    @patch("village.extensibility.registry.logger")
    def test_register_processor_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_processor() logs debug message."""
        registry = ExtensionRegistry()
        mock_processor = MockChatProcessor()

        registry.register_processor(mock_processor)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockChatProcessor" in call_args
        assert "Registered processor" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_tool_invoker_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_tool_invoker() logs debug message."""
        registry = ExtensionRegistry()
        mock_invoker = MockToolInvoker()

        registry.register_tool_invoker(mock_invoker)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockToolInvoker" in call_args
        assert "Registered tool invoker" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_thinking_refiner_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_thinking_refiner() logs debug message."""
        registry = ExtensionRegistry()
        mock_refiner = MockThinkingRefiner()

        registry.register_thinking_refiner(mock_refiner)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockThinkingRefiner" in call_args
        assert "Registered thinking refiner" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_chat_context_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_chat_context() logs debug message."""
        registry = ExtensionRegistry()
        mock_context = MockChatContext()

        registry.register_chat_context(mock_context)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockChatContext" in call_args
        assert "Registered chat context" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_beads_integrator_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_beads_integrator() logs debug message."""
        registry = ExtensionRegistry()
        mock_integrator = MockBeadsIntegrator()

        registry.register_beads_integrator(mock_integrator)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockBeadsIntegrator" in call_args
        assert "Registered beads integrator" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_server_discovery_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_server_discovery() logs debug message."""
        registry = ExtensionRegistry()
        mock_discovery = MockServerDiscovery()

        registry.register_server_discovery(mock_discovery)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockServerDiscovery" in call_args
        assert "Registered server discovery" in call_args

    @patch("village.extensibility.registry.logger")
    def test_register_llm_adapter_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """register_llm_adapter() logs debug message."""
        registry = ExtensionRegistry()
        mock_adapter = MockLLMAdapter()

        registry.register_llm_adapter(mock_adapter)

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MockLLMAdapter" in call_args
        assert "Registered LLM adapter" in call_args

    @patch("village.extensibility.registry.logger")
    def test_reset_to_defaults_logs_debug_message(self, mock_logger: MagicMock) -> None:
        """reset_to_defaults() logs debug message."""
        registry = ExtensionRegistry()

        registry.reset_to_defaults()

        mock_logger.debug.assert_called_once_with("Reset all extensions to defaults")

    @patch("village.extensibility.registry.logger")
    def test_multiple_registrations_log_multiple_messages(self, mock_logger: MagicMock) -> None:
        """Multiple registrations log multiple debug messages."""
        registry = ExtensionRegistry()

        registry.register_processor(MockChatProcessor())
        registry.register_tool_invoker(MockToolInvoker())
        registry.register_llm_adapter(MockLLMAdapter())

        assert mock_logger.debug.call_count == 3


class TestExtensionRegistryMockBehavior:
    """Tests to verify mock implementations work correctly."""

    @pytest.mark.asyncio
    async def test_mock_chat_processor_pre_process(self) -> None:
        """MockChatProcessor pre_process works as expected."""
        processor = MockChatProcessor()
        result = await processor.pre_process("test input")
        assert result == "MOCK_PRE: test input"

    @pytest.mark.asyncio
    async def test_mock_chat_processor_post_process(self) -> None:
        """MockChatProcessor post_process works as expected."""
        processor = MockChatProcessor()
        result = await processor.post_process("test response")
        assert result == "MOCK_POST: test response"

    @pytest.mark.asyncio
    async def test_mock_tool_invoker_transform_args(self) -> None:
        """MockToolInvoker transform_args works as expected."""
        invoker = MockToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={"key": "value"})
        result = await invoker.transform_args(invocation)
        assert result == {"mock": True, "key": "value"}

    @pytest.mark.asyncio
    async def test_mock_thinking_refiner_refine_query(self) -> None:
        """MockThinkingRefiner refine_query works as expected."""
        refiner = MockThinkingRefiner()
        result = await refiner.refine_query("test query")
        assert result.original_query == "test query"
        assert len(result.refined_steps) == 2

    @pytest.mark.asyncio
    async def test_mock_chat_context_load_context(self) -> None:
        """MockChatContext load_context works as expected."""
        context = MockChatContext()
        result = await context.load_context("session-123")
        assert result.session_id == "session-123"
        assert result.user_data["mock_data"] == "session_session-123"

    @pytest.mark.asyncio
    async def test_mock_beads_integrator_create_bead_spec(self) -> None:
        """MockBeadsIntegrator create_bead_spec works as expected."""
        integrator = MockBeadsIntegrator()
        result = await integrator.create_bead_spec(
            {"title": "Test Bead", "description": "Test desc"}
        )
        assert result.title == "Test Bead"
        assert result.description == "Test desc"

    @pytest.mark.asyncio
    async def test_mock_server_discovery_discover_servers(self) -> None:
        """MockServerDiscovery discover_servers works as expected."""
        discovery = MockServerDiscovery()
        servers = await discovery.discover_servers()
        assert len(servers) == 2
        assert all(isinstance(s, MCPServer) for s in servers)

    @pytest.mark.asyncio
    async def test_mock_llm_adapter_adapt_config(self) -> None:
        """MockLLMAdapter adapt_config works as expected."""
        adapter = MockLLMAdapter()
        base_config = LLMProviderConfig(
            provider="base",
            model="base-model",
            api_key_env="BASE_KEY",
            timeout=30,
            max_tokens=512,
        )
        result = await adapter.adapt_config(base_config)
        assert result.provider == "mock-provider"
        assert result.model == "mock-model"
