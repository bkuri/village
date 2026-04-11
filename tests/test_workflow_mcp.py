import pytest

from village.workflow.mcp_tools import call_mcp_tool


class TestMCPTools:
    @pytest.mark.asyncio
    async def test_no_fn_returns_unavailable(self):
        result = await call_mcp_tool("perplexity", "test query")
        assert "MCP unavailable" in result

    @pytest.mark.asyncio
    async def test_mock_fn_success(self):
        async def mock_fn(server: str, query: str) -> str:
            return f"result from {server}: {query}"

        result = await call_mcp_tool("perplexity", "test query", mcp_fn=mock_fn)
        assert "perplexity" in result
        assert "test query" in result

    @pytest.mark.asyncio
    async def test_sync_fn_success(self):
        def mock_fn(server: str, query: str) -> str:
            return f"sync result from {server}"

        result = await call_mcp_tool("perplexity", "test query", mcp_fn=mock_fn)
        assert "sync result" in result

    @pytest.mark.asyncio
    async def test_fn_error_returns_error(self):
        async def failing_fn(server: str, query: str) -> str:
            raise RuntimeError("API key invalid")

        result = await call_mcp_tool("perplexity", "test query", mcp_fn=failing_fn)
        assert "MCP error" in result
        assert "API key invalid" in result
