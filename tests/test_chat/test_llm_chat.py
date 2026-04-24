"""Tests for LLMChat module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from village.chat.llm_chat import SLASH_COMMANDS, LLMChat
from village.extensibility import ExtensionRegistry


def _make_llm_client() -> MagicMock:
    client = MagicMock()
    client.call = MagicMock(return_value='{"title": "Test task", "description": "A test", "scope": "task"}')
    return client


def _make_chat(llm_client: MagicMock | None = None) -> LLMChat:
    return LLMChat(llm_client=llm_client or _make_llm_client())


class TestInvokeTool:
    @pytest.mark.asyncio
    async def test_invoke_tool_success(self) -> None:
        chat = _make_chat()
        result = await chat.invoke_tool("test_tool", {"arg": "val"})
        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_invoke_tool_skipped_by_filter(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=False)
        extensions.register_tool_invoker(mock_invoker)
        chat = _make_chat()
        chat.extensions = extensions
        result = await chat.invoke_tool("blocked_tool", {"arg": "val"})
        assert result.success is False
        assert "skipped by domain filter" in result.error

    @pytest.mark.asyncio
    async def test_invoke_tool_transform_args(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"arg": "transformed"})
        mock_invoker.on_success = AsyncMock(return_value={"status": "ok"})
        extensions.register_tool_invoker(mock_invoker)
        chat = _make_chat()
        chat.extensions = extensions
        result = await chat.invoke_tool("tool", {"arg": "original"})
        assert result.success is True
        mock_invoker.transform_args.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_tool_error_hook_called(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"arg": "val"})
        mock_invoker.on_success = AsyncMock(side_effect=ValueError("success error"))
        mock_invoker.on_error = AsyncMock()
        extensions.register_tool_invoker(mock_invoker)
        chat = _make_chat()
        chat.extensions = extensions
        result = await chat.invoke_tool("tool", {"arg": "val"})
        assert result.success is False
        assert "success error" in result.error
        mock_invoker.on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_tool_on_success_called(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"a": 1})
        mock_invoker.on_success = AsyncMock(return_value={"processed": True})
        extensions.register_tool_invoker(mock_invoker)
        chat = _make_chat()
        chat.extensions = extensions
        result = await chat.invoke_tool("tool", {"a": 1})
        assert result.success is True
        assert result.result == {"processed": True}
        mock_invoker.on_success.assert_called_once()


class TestCallLLMWithRetry:
    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        chat = _make_chat()
        chat.llm_client.call = MagicMock(
            side_effect=[Exception("timeout"), '{"title": "T", "description": "D", "scope": "task"}']
        )
        result = await chat._call_llm_with_retry("prompt", max_retries=3)
        assert '"title"' in result

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self) -> None:
        chat = _make_chat()
        chat.llm_client.call = MagicMock(side_effect=Exception("persistent error"))
        with pytest.raises(Exception):
            await chat._call_llm_with_retry("prompt", max_retries=2)

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self) -> None:
        extensions = ExtensionRegistry()
        mock_adapter = MagicMock()
        mock_adapter.should_retry = AsyncMock(return_value=False)
        extensions.register_llm_adapter(mock_adapter)
        chat = _make_chat()
        chat.extensions = extensions
        chat.llm_client.call = MagicMock(side_effect=Exception("fatal"))
        with pytest.raises(Exception, match="fatal"):
            await chat._call_llm_with_retry("prompt", max_retries=3)

    @pytest.mark.asyncio
    async def test_no_retry_needed(self) -> None:
        chat = _make_chat()
        chat.llm_client.call = MagicMock(return_value="success response")
        result = await chat._call_llm_with_retry("prompt", max_retries=3)
        assert result == "success response"
        assert chat.llm_client.call.call_count == 1


class TestHandleSubmit:
    @pytest.mark.asyncio
    async def test_handle_confirm_no_current_task(self) -> None:
        chat = _make_chat()
        result = await chat.handle_confirm("")
        assert "No current task" in result

    @pytest.mark.asyncio
    async def test_handle_confirm_with_breakdown(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        from village.chat.sequential_thinking import TaskBreakdown

        chat.session.current_breakdown = TaskBreakdown(items=[], summary="test", created_at="2026-01-01T00:00:00")
        with (
            patch("village.chat.llm_chat.get_task_store") as mock_get_store,
            patch("village.chat.llm_chat.confirm_breakdown", new_callable=AsyncMock) as mock_confirm,
        ):
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store
            mock_confirm.return_value = "Created 2 subtasks"
            result = await chat.handle_confirm("")
        assert "Created 2 subtasks" in result

    @pytest.mark.asyncio
    async def test_handle_confirm_store_error(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        from village.chat.sequential_thinking import TaskBreakdown
        from village.tasks import TaskStoreError

        chat.session.current_breakdown = TaskBreakdown(items=[], summary="test", created_at="2026-01-01T00:00:00")
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_get_store.side_effect = TaskStoreError("store unavailable")
            result = await chat.handle_confirm("")
        assert "Task store not available" in result


class TestHandleTasks:
    @pytest.mark.asyncio
    async def test_handle_tasks_list(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Test task"
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            result = await chat.handle_tasks("")
        assert "tsk-1" in result
        assert "Test task" in result

    @pytest.mark.asyncio
    async def test_handle_tasks_no_config(self) -> None:
        chat = _make_chat()
        chat.config = None
        result = await chat.handle_tasks("")
        assert "Failed to list tasks" in result


class TestHandleReady:
    @pytest.mark.asyncio
    async def test_handle_ready(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        mock_task = MagicMock()
        mock_task.id = "tsk-1"
        mock_task.title = "Ready task"
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_ready_tasks.return_value = [mock_task]
            mock_get_store.return_value = mock_store
            result = await chat.handle_ready("")
        assert "tsk-1" in result

    @pytest.mark.asyncio
    async def test_handle_ready_no_tasks(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_ready_tasks.return_value = []
            mock_get_store.return_value = mock_store
            result = await chat.handle_ready("")
        assert "No ready tasks" in result


class TestHandleTask:
    @pytest.mark.asyncio
    async def test_handle_task_no_args(self) -> None:
        chat = _make_chat()
        result = await chat.handle_task("")
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_handle_task_with_deps(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        dep_block = MagicMock()
        dep_block.id = "tsk-dep"
        dep_block.title = "Dep task"
        dep_blocked = MagicMock()
        dep_blocked.id = "tsk-blocker"
        dep_blocked.title = "Blocker task"
        deps_info = MagicMock()
        deps_info.blocks = [dep_block]
        deps_info.blocked_by = [dep_blocked]
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_dependencies.return_value = deps_info
            mock_get_store.return_value = mock_store
            result = await chat.handle_task("tsk-1")
        assert "depends on" in result
        assert "blocked by" in result

    @pytest.mark.asyncio
    async def test_handle_task_no_deps(self) -> None:
        chat = _make_chat()
        mock_config = MagicMock()
        chat.config = mock_config
        deps_info = MagicMock()
        deps_info.blocks = []
        deps_info.blocked_by = []
        with patch("village.chat.llm_chat.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_dependencies.return_value = deps_info
            mock_get_store.return_value = mock_store
            result = await chat.handle_task("tsk-1")
        assert "no dependencies" in result


class TestParseTaskSpecResponse:
    def test_parse_json_code_fence(self) -> None:
        chat = _make_chat()
        response = '```json\n{"title": "T", "description": "D", "scope": "task"}\n```'
        result, error = chat._parse_task_spec_response(response)
        assert result is not None
        assert result["title"] == "T"

    def test_parse_plain_json(self) -> None:
        chat = _make_chat()
        response = '{"title": "T", "description": "D", "scope": "task"}'
        result, error = chat._parse_task_spec_response(response)
        assert result is not None

    def test_parse_missing_fields(self) -> None:
        chat = _make_chat()
        response = '{"title": "T"}'
        result, error = chat._parse_task_spec_response(response)
        assert result is None
        assert "Missing" in error

    def test_parse_invalid_json(self) -> None:
        chat = _make_chat()
        response = "not json at all"
        result, error = chat._parse_task_spec_response(response)
        assert result is None
        assert error == "parse_error"

    def test_parse_defaults_applied(self) -> None:
        chat = _make_chat()
        response = '{"title": "T", "description": "D", "scope": "feature"}'
        result, error = chat._parse_task_spec_response(response)
        assert result is not None
        assert result["blocks"] == []
        assert result["blocked_by"] == []
        assert result["estimate"] == "unknown"
        assert result["confidence"] == "medium"


class TestSlashCommands:
    def test_all_slash_commands_mapped(self) -> None:
        for cmd, handler in SLASH_COMMANDS.items():
            assert hasattr(LLMChat, handler), f"LLMChat missing handler {handler} for {cmd}"

    @pytest.mark.asyncio
    async def test_handle_slash_command_unknown(self) -> None:
        chat = _make_chat()
        result = await chat.handle_slash_command("/nonexistent")
        assert "Unknown command" in result


class TestHandleDiscard:
    @pytest.mark.asyncio
    async def test_discard_breakdown(self) -> None:
        chat = _make_chat()
        from village.chat.sequential_thinking import TaskBreakdown

        chat.session.current_breakdown = TaskBreakdown(
            items=[MagicMock(title="T1")], summary="s", created_at="2026-01-01"
        )
        result = await chat.handle_discard("")
        assert "Discarded breakdown" in result
        assert chat.session.current_breakdown is None

    @pytest.mark.asyncio
    async def test_discard_nothing(self) -> None:
        chat = _make_chat()
        result = await chat.handle_discard("")
        assert "No current task" in result


class TestInvokeToolMCP:
    @pytest.mark.asyncio
    async def test_invoke_tool_calls_mcp_client(self) -> None:
        mock_mcp = MagicMock()
        mock_mcp.invoke_tool = AsyncMock(return_value="mcp result data")
        chat = _make_chat()
        chat.mcp_client = mock_mcp
        result = await chat.invoke_tool("search", {"q": "test"}, server_name="perplexity")
        assert result.success is True
        mock_mcp.invoke_tool.assert_called_once_with(
            server_name="perplexity",
            tool_name="search",
            tool_input={"q": "test"},
        )

    @pytest.mark.asyncio
    async def test_invoke_tool_mcp_result_passed_through_on_success(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"q": "test"})
        mock_invoker.on_success = AsyncMock(return_value="processed mcp result")
        extensions.register_tool_invoker(mock_invoker)
        mock_mcp = MagicMock()
        mock_mcp.invoke_tool = AsyncMock(return_value="raw mcp data")
        chat = _make_chat()
        chat.extensions = extensions
        chat.mcp_client = mock_mcp
        result = await chat.invoke_tool("search", {"q": "test"}, server_name="perplexity")
        assert result.success is True
        assert result.result == "processed mcp result"
        mock_invoker.on_success.assert_called_once()
        call_args = mock_invoker.on_success.call_args
        assert call_args[0][1] == "raw mcp data"

    @pytest.mark.asyncio
    async def test_invoke_tool_mcp_error_handled(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"q": "test"})
        mock_invoker.on_error = AsyncMock()
        extensions.register_tool_invoker(mock_invoker)
        mock_mcp = MagicMock()
        mock_mcp.invoke_tool = AsyncMock(side_effect=RuntimeError("server unavailable"))
        chat = _make_chat()
        chat.extensions = extensions
        chat.mcp_client = mock_mcp
        result = await chat.invoke_tool("search", {"q": "test"}, server_name="perplexity")
        assert result.success is False
        assert result.error is not None
        assert "server unavailable" in result.error
        mock_invoker.on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_tool_no_mcp_client_falls_back_to_placeholder(self) -> None:
        chat = _make_chat()
        assert chat.mcp_client is None
        result = await chat.invoke_tool("search", {"q": "test"}, server_name="perplexity")
        assert result.success is True
        assert result.result["status"] == "hook_ready"

    @pytest.mark.asyncio
    async def test_invoke_tool_no_server_name_falls_back_to_placeholder(self) -> None:
        mock_mcp = MagicMock()
        chat = _make_chat()
        chat.mcp_client = mock_mcp
        result = await chat.invoke_tool("search", {"q": "test"})
        assert result.success is True
        assert result.result["status"] == "hook_ready"
        mock_mcp.invoke_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoke_tool_mcp_client_in_constructor(self) -> None:
        mock_mcp = MagicMock()
        mock_mcp.invoke_tool = AsyncMock(return_value="constructor mcp result")
        chat = LLMChat(llm_client=_make_llm_client(), mcp_client=mock_mcp)
        assert chat.mcp_client is mock_mcp
        result = await chat.invoke_tool("tool", {"a": 1}, server_name="server1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_set_mcp_client(self) -> None:
        mock_mcp = MagicMock()
        chat = _make_chat()
        assert chat.mcp_client is None
        await chat.set_mcp_client(mock_mcp)
        assert chat.mcp_client is mock_mcp

    @pytest.mark.asyncio
    async def test_invoke_tool_server_name_in_context(self) -> None:
        extensions = ExtensionRegistry()
        mock_invoker = MagicMock()
        mock_invoker.should_invoke = AsyncMock(return_value=True)
        mock_invoker.transform_args = AsyncMock(return_value={"a": 1})
        mock_invoker.on_success = AsyncMock(return_value={"status": "ok"})
        extensions.register_tool_invoker(mock_invoker)
        mock_mcp = MagicMock()
        mock_mcp.invoke_tool = AsyncMock(return_value="result")
        chat = _make_chat()
        chat.extensions = extensions
        chat.mcp_client = mock_mcp
        from village.extensibility.tool_invokers import ToolInvocation

        with patch("village.chat.llm_chat.ToolInvocation", wraps=ToolInvocation) as spy:
            await chat.invoke_tool("tool", {"a": 1}, server_name="my-server")
            call_kwargs = spy.call_args
            assert call_kwargs.kwargs["context"]["server_name"] == "my-server"
