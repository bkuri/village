"""Tool invoker hooks for customizing MCP tool invocation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolInvocation:
    """Tool invocation request."""

    tool_name: str
    args: dict[str, Any]
    context: dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize context if not provided."""
        if self.context is None:
            self.context = {}


@dataclass
class ToolResult:
    """Tool invocation result."""

    success: bool
    result: Any
    error: Optional[str] = None
    cached: bool = False


class ToolInvoker(ABC):
    """Base class for tool invocation customization.

    Allows domains to customize how MCP tools are invoked, including caching,
    filtering, and argument transformation.

    Example:
        class TradingToolInvoker(ToolInvoker):
            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                # Skip expensive backtest if recent cache exists
                return not self.has_recent_cache(invocation.tool_name)

            async def transform_args(self, invocation: ToolInvocation) -> dict:
                # Enrich backtest args with historical context
                return enrich_backtest_args(invocation.args)
    """

    @abstractmethod
    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        """Determine whether to invoke the tool.

        Args:
            invocation: Tool invocation request

        Returns:
            True if tool should be invoked, False to skip
        """
        pass

    @abstractmethod
    async def transform_args(self, invocation: ToolInvocation) -> dict[str, Any]:
        """Transform tool arguments before invocation.

        Args:
            invocation: Tool invocation request

        Returns:
            Transformed arguments dictionary
        """
        pass

    @abstractmethod
    async def on_success(self, invocation: ToolInvocation, result: Any) -> Any:
        """Handle successful tool invocation.

        Can cache results, log metrics, etc.

        Args:
            invocation: Tool invocation request
            result: Tool result

        Returns:
            Potentially transformed result
        """
        pass

    @abstractmethod
    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        """Handle tool invocation error.

        Args:
            invocation: Tool invocation request
            error: Exception that occurred
        """
        pass


class DefaultToolInvoker(ToolInvoker):
    """Default no-op tool invoker."""

    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        """Always invoke tools."""
        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict[str, Any]:
        """Return args unchanged."""
        return invocation.args

    async def on_success(self, invocation: ToolInvocation, result: Any) -> Any:
        """Return result unchanged."""
        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        """Do nothing on error."""
        pass
