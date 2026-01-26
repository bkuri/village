"""LLM client abstraction for provider-agnostic LLM calls."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolDefinition:
    """Tool definition for API calls."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    """Tool invocation result."""

    tool_name: str
    tool_input: dict[str, Any]
    result: str


class LLMClient(ABC):
    """Provider-agnostic LLM client interface."""

    @abstractmethod
    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list[ToolDefinition]] = None,
        max_tokens: int = 4096,
        timeout: int = 300,
    ) -> str:
        """
        Call LLM with optional tool support.

        Args:
            prompt: User prompt
            system_prompt: System message
            tools: Available tools (provider decides if/how to use)
            max_tokens: Max response tokens
            timeout: Call timeout in seconds

        Returns:
            LLM response (may include tool calls based on implementation)
        """
        pass

    @property
    @abstractmethod
    def supports_tools(self) -> bool:
        """Whether this provider supports tool/function calling."""
        pass

    @property
    @abstractmethod
    def supports_mcp(self) -> bool:
        """Whether this provider supports MCP servers."""
        pass
