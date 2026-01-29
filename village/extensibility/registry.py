"""Extension registry for managing domain-specific hooks."""

import logging
from typing import Optional, Type

from village.extensibility.processors import ChatProcessor, DefaultChatProcessor
from village.extensibility.tool_invokers import DefaultToolInvoker, ToolInvoker
from village.extensibility.thinking_refiners import (
    DefaultThinkingRefiner,
    ThinkingRefiner,
)
from village.extensibility.context import ChatContext, DefaultChatContext
from village.extensibility.beads_integrators import (
    BeadsIntegrator,
    DefaultBeadsIntegrator,
)
from village.extensibility.server_discovery import (
    DefaultServerDiscovery,
    ServerDiscovery,
)
from village.extensibility.llm_adapters import DefaultLLMProviderAdapter, LLMProviderAdapter

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Registry for managing extension implementations.

    Provides single point for registering and retrieving extension implementations
    per domain. Uses sensible defaults if no domain-specific implementation provided.

    Example:
        registry = ExtensionRegistry()
        registry.register_processor(TradingChatProcessor())
        registry.register_tool_invoker(TradingToolInvoker())

        # Use extensions
        processor = registry.get_processor()
        processed = await processor.pre_process("BTC-ETH pair")
    """

    def __init__(self) -> None:
        """Initialize registry with default implementations."""
        self._processor: ChatProcessor = DefaultChatProcessor()
        self._tool_invoker: ToolInvoker = DefaultToolInvoker()
        self._thinking_refiner: ThinkingRefiner = DefaultThinkingRefiner()
        self._chat_context: ChatContext = DefaultChatContext()
        self._beads_integrator: BeadsIntegrator = DefaultBeadsIntegrator()
        self._server_discovery: ServerDiscovery = DefaultServerDiscovery()
        self._llm_adapter: LLMProviderAdapter = DefaultLLMProviderAdapter()

    def register_processor(self, processor: ChatProcessor) -> None:
        """Register chat processor.

        Args:
            processor: ChatProcessor implementation
        """
        self._processor = processor
        logger.debug(f"Registered processor: {processor.__class__.__name__}")

    def register_tool_invoker(self, invoker: ToolInvoker) -> None:
        """Register tool invoker.

        Args:
            invoker: ToolInvoker implementation
        """
        self._tool_invoker = invoker
        logger.debug(f"Registered tool invoker: {invoker.__class__.__name__}")

    def register_thinking_refiner(self, refiner: ThinkingRefiner) -> None:
        """Register thinking refiner.

        Args:
            refiner: ThinkingRefiner implementation
        """
        self._thinking_refiner = refiner
        logger.debug(f"Registered thinking refiner: {refiner.__class__.__name__}")

    def register_chat_context(self, context: ChatContext) -> None:
        """Register chat context.

        Args:
            context: ChatContext implementation
        """
        self._chat_context = context
        logger.debug(f"Registered chat context: {context.__class__.__name__}")

    def register_beads_integrator(self, integrator: BeadsIntegrator) -> None:
        """Register beads integrator.

        Args:
            integrator: BeadsIntegrator implementation
        """
        self._beads_integrator = integrator
        logger.debug(f"Registered beads integrator: {integrator.__class__.__name__}")

    def register_server_discovery(self, discovery: ServerDiscovery) -> None:
        """Register server discovery.

        Args:
            discovery: ServerDiscovery implementation
        """
        self._server_discovery = discovery
        logger.debug(f"Registered server discovery: {discovery.__class__.__name__}")

    def register_llm_adapter(self, adapter: LLMProviderAdapter) -> None:
        """Register LLM provider adapter.

        Args:
            adapter: LLMProviderAdapter implementation
        """
        self._llm_adapter = adapter
        logger.debug(f"Registered LLM adapter: {adapter.__class__.__name__}")

    # Getter methods
    def get_processor(self) -> ChatProcessor:
        """Get registered processor."""
        return self._processor

    def get_tool_invoker(self) -> ToolInvoker:
        """Get registered tool invoker."""
        return self._tool_invoker

    def get_thinking_refiner(self) -> ThinkingRefiner:
        """Get registered thinking refiner."""
        return self._thinking_refiner

    def get_chat_context(self) -> ChatContext:
        """Get registered chat context."""
        return self._chat_context

    def get_beads_integrator(self) -> BeadsIntegrator:
        """Get registered beads integrator."""
        return self._beads_integrator

    def get_server_discovery(self) -> ServerDiscovery:
        """Get registered server discovery."""
        return self._server_discovery

    def get_llm_adapter(self) -> LLMProviderAdapter:
        """Get registered LLM adapter."""
        return self._llm_adapter

    def get_all_names(self) -> dict[str, str]:
        """Get names of all registered implementations.

        Returns:
            Dictionary mapping extension type to implementation class name
        """
        return {
            "processor": self._processor.__class__.__name__,
            "tool_invoker": self._tool_invoker.__class__.__name__,
            "thinking_refiner": self._thinking_refiner.__class__.__name__,
            "chat_context": self._chat_context.__class__.__name__,
            "beads_integrator": self._beads_integrator.__class__.__name__,
            "server_discovery": self._server_discovery.__class__.__name__,
            "llm_adapter": self._llm_adapter.__class__.__name__,
        }

    def reset_to_defaults(self) -> None:
        """Reset all extensions to default implementations."""
        self._processor = DefaultChatProcessor()
        self._tool_invoker = DefaultToolInvoker()
        self._thinking_refiner = DefaultThinkingRefiner()
        self._chat_context = DefaultChatContext()
        self._beads_integrator = DefaultBeadsIntegrator()
        self._server_discovery = DefaultServerDiscovery()
        self._llm_adapter = DefaultLLMProviderAdapter()
        logger.debug("Reset all extensions to defaults")
