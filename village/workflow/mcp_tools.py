import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

MCPToolFn = Callable[[str, str], Any]


async def call_mcp_tool(server: str, query: str, mcp_fn: MCPToolFn | None = None) -> str:
    if mcp_fn is None:
        logger.warning(f"MCP tool call skipped (no client): {server}")
        return f"[MCP unavailable: {server}]"

    try:
        result = mcp_fn(server, query)
        if hasattr(result, "__await__"):
            result = await result
        return str(result)
    except Exception as e:
        logger.warning(f"MCP tool '{server}' failed: {e}")
        return f"[MCP error: {server}: {e}]"
