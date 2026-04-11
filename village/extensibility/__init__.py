"""Village extensibility framework for domain-specific customization.

Provides abstract base classes and registry for extending Village's chat loop
with domain-specific behavior without tight coupling.

Extension Points:
1. ChatProcessor: Pre/post message processing
2. ToolInvoker: Customize MCP tool invocation
3. ThinkingRefiner: Domain-specific query refinement
4. ChatContext: Session state/context management
 5. TaskHooks: Customize task creation/updates
6. ServerDiscovery: Dynamic MCP server discovery
7. LLMProviderAdapter: Customize LLM provider config

Example Usage:

    from village.extensibility import ExtensionRegistry
    from village.extensibility.processors import ChatProcessor

    class MyCustomProcessor(ChatProcessor):
        async def pre_process(self, user_input: str) -> str:
            # Custom preprocessing logic
            return user_input.upper()

    registry = ExtensionRegistry()
    registry.register_processor(MyCustomProcessor())
"""

from village.extensibility.context import ChatContext, DefaultChatContext
from village.extensibility.llm_adapters import DefaultLLMProviderAdapter, LLMProviderAdapter
from village.extensibility.loader import discover_mcp_servers, initialize_extensions
from village.extensibility.processors import ChatProcessor, DefaultChatProcessor
from village.extensibility.registry import ExtensionRegistry
from village.extensibility.server_discovery import (
    DefaultServerDiscovery,
    MCPServer,
    ServerDiscovery,
)
from village.extensibility.task_hooks import DefaultTaskHooks, TaskHooks
from village.extensibility.thinking_refiners import DefaultThinkingRefiner, ThinkingRefiner
from village.extensibility.tool_invokers import DefaultToolInvoker, ToolInvoker

__all__ = [
    "ExtensionRegistry",
    "ChatProcessor",
    "DefaultChatProcessor",
    "ToolInvoker",
    "DefaultToolInvoker",
    "ThinkingRefiner",
    "DefaultThinkingRefiner",
    "ChatContext",
    "DefaultChatContext",
    "TaskHooks",
    "DefaultTaskHooks",
    "ServerDiscovery",
    "DefaultServerDiscovery",
    "LLMProviderAdapter",
    "DefaultLLMProviderAdapter",
    "MCPServer",
    "initialize_extensions",
    "discover_mcp_servers",
]
