"""Research tool invoker for query caching and auditing."""

from village.extensibility.tool_invokers import (
    ToolInvocation,
    ToolInvoker,
)


class ResearchToolInvoker(ToolInvoker):
    """Tool invoker for research domain.

    Features:
    - Query caching to avoid redundant searches
    - Default methodology injection
    - Audit trail logging
    """

    def __init__(self) -> None:
        """Initialize research tool invoker."""
        self._query_cache: dict[str, dict] = {}

    async def should_invoke(self, invocation: ToolInvocation) -> bool:
        """Determine if tool should be invoked.

        Checks cache for research queries to avoid redundant searches.

        Args:
            invocation: Tool invocation request

        Returns:
            True if tool should be invoked
        """
        if invocation.tool_name == "perplexity_search":
            cache_key = self._make_cache_key(invocation)
            return cache_key not in self._query_cache

        return True

    async def transform_args(self, invocation: ToolInvocation) -> dict:
        """Transform tool arguments before invocation.

        Adds default methodology if not specified for research tasks.

        Args:
            invocation: Tool invocation request

        Returns:
            Transformed arguments
        """
        args = invocation.args.copy()

        if invocation.tool_name == "perplexity_search" and "methodology" not in args:
            args["methodology"] = "systematic_review"

        return args

    async def on_success(self, invocation: ToolInvocation, result) -> dict:
        """Handle successful tool invocation.

        Logs research queries for audit trail and caches results.

        Args:
            invocation: Tool invocation request
            result: Tool result

        Returns:
            Potentially transformed result
        """
        if invocation.tool_name == "perplexity_search":
            cache_key = self._make_cache_key(invocation)
            self._query_cache[cache_key] = {
                "timestamp": self._get_timestamp(),
                "query": invocation.args.get("query", ""),
                "result": result,
            }
            print(f"[RESEARCH] Logged query: {invocation.args.get('query', 'N/A')}")

        return result

    async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
        """Handle tool invocation error.

        Args:
            invocation: Tool invocation request
            error: Exception that occurred
        """
        print(f"[RESEARCH] Tool error in {invocation.tool_name}: {error}")

    def _make_cache_key(self, invocation: ToolInvocation) -> str:
        """Create cache key from invocation.

        Args:
            invocation: Tool invocation request

        Returns:
            Cache key string
        """
        query = invocation.args.get("query", "")
        return f"{invocation.tool_name}:{query}"

    def _get_timestamp(self) -> str:
        """Get current timestamp.

        Returns:
            ISO format timestamp
        """
        from datetime import datetime

        return datetime.now().isoformat()
