"""Test ToolInvoker ABC and DefaultToolInvoker."""

import pytest

from village.extensibility.tool_invokers import (
    DefaultToolInvoker,
    ToolInvocation,
    ToolInvoker,
    ToolResult,
)


class TestToolInvocation:
    """Test ToolInvocation dataclass."""

    def test_tool_invocation_initialization(self):
        """Test ToolInvocation initialization with required fields."""
        invocation = ToolInvocation(tool_name="test_tool", args={"arg1": "value1"})
        assert invocation.tool_name == "test_tool"
        assert invocation.args == {"arg1": "value1"}
        assert invocation.context == {}

    def test_tool_invocation_with_context(self):
        """Test ToolInvocation initialization with context."""
        context = {"session_id": "abc123", "user": "test"}
        invocation = ToolInvocation(tool_name="test_tool", args={}, context=context)
        assert invocation.context == context

    def test_tool_invocation_none_context_becomes_empty_dict(self):
        """Test that None context becomes empty dict via post_init."""
        invocation = ToolInvocation(tool_name="test", args={}, context=None)
        assert invocation.context == {}

    def test_tool_invocation_args_mutation(self):
        """Test that args dict can be mutated."""
        invocation = ToolInvocation(tool_name="test", args={})
        invocation.args["new_arg"] = "value"
        assert invocation.args == {"new_arg": "value"}


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_tool_result_success(self):
        """Test ToolResult with success=True."""
        result = ToolResult(success=True, result={"output": "data"})
        assert result.success is True
        assert result.result == {"output": "data"}
        assert result.error is None
        assert result.cached is False

    def test_tool_result_error(self):
        """Test ToolResult with success=False."""
        result = ToolResult(success=False, result=None, error="Tool failed")
        assert result.success is False
        assert result.result is None
        assert result.error == "Tool failed"

    def test_tool_result_cached(self):
        """Test ToolResult with cached=True."""
        result = ToolResult(success=True, result="data", cached=True)
        assert result.success is True
        assert result.cached is True

    def test_tool_result_all_fields(self):
        """Test ToolResult with all fields."""
        result = ToolResult(
            success=True,
            result={"value": 42},
            error=None,
            cached=False,
        )
        assert result.success is True
        assert result.result == {"value": 42}
        assert result.error is None
        assert result.cached is False


class TestDefaultToolInvoker:
    """Test DefaultToolInvoker behavior."""

    @pytest.mark.asyncio
    async def test_should_invoke_always_returns_true(self):
        """Test that should_invoke always returns True."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="any_tool", args={"arg": "value"})
        result = await invoker.should_invoke(invocation)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_invoke_with_empty_args(self):
        """Test should_invoke with empty args."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        result = await invoker.should_invoke(invocation)
        assert result is True

    @pytest.mark.asyncio
    async def test_transform_args_returns_unchanged(self):
        """Test that transform_args returns args unchanged."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={"arg1": "val1", "arg2": "val2"})
        result = await invoker.transform_args(invocation)
        assert result == {"arg1": "val1", "arg2": "val2"}
        assert result is invocation.args

    @pytest.mark.asyncio
    async def test_transform_args_with_empty_dict(self):
        """Test transform_args with empty args dict."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        result = await invoker.transform_args(invocation)
        assert result == {}

    @pytest.mark.asyncio
    async def test_transform_args_with_nested_args(self):
        """Test transform_args with nested args."""
        invoker = DefaultToolInvoker()
        args = {"outer": {"inner": "value"}}
        invocation = ToolInvocation(tool_name="test", args=args)
        result = await invoker.transform_args(invocation)
        assert result == args

    @pytest.mark.asyncio
    async def test_on_success_returns_result_unchanged(self):
        """Test that on_success returns result unchanged."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        result_data = {"output": "data"}
        result = await invoker.on_success(invocation, result_data)
        assert result == result_data
        assert result is result_data

    @pytest.mark.asyncio
    async def test_on_success_with_string_result(self):
        """Test on_success with string result."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        result_data = "string result"
        result = await invoker.on_success(invocation, result_data)
        assert result == "string result"

    @pytest.mark.asyncio
    async def test_on_success_with_none_result(self):
        """Test on_success with None result."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        result = await invoker.on_success(invocation, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_error_does_nothing(self):
        """Test that on_error does nothing."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})
        error = Exception("Tool failed")
        result = await invoker.on_error(invocation, error)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_error_with_different_error_types(self):
        """Test on_error with various error types."""
        invoker = DefaultToolInvoker()
        invocation = ToolInvocation(tool_name="test", args={})

        errors = [
            ValueError("Invalid value"),
            RuntimeError("Runtime error"),
            ConnectionError("Connection failed"),
            Exception("Generic error"),
        ]

        for error in errors:
            result = await invoker.on_error(invocation, error)
            assert result is None


class TestCustomToolInvoker:
    """Test custom ToolInvoker implementations."""

    @pytest.mark.asyncio
    async def test_custom_invoker_conditionally_invokes(self):
        """Test custom invoker that conditionally invokes."""

        class ConditionalInvoker(ToolInvoker):
            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                return invocation.tool_name != "skip_tool"

            async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
                return invocation.args

            async def on_success(self, invocation: ToolInvocation, result: object) -> object:
                return result

            async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
                pass

        invoker = ConditionalInvoker()
        skip_invocation = ToolInvocation(tool_name="skip_tool", args={})
        invoke_invocation = ToolInvocation(tool_name="run_tool", args={})

        assert await invoker.should_invoke(skip_invocation) is False
        assert await invoker.should_invoke(invoke_invocation) is True

    @pytest.mark.asyncio
    async def test_custom_invoker_transform_args(self):
        """Test custom invoker that transforms args."""

        class ArgTransformer(ToolInvoker):
            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                return True

            async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
                new_args = invocation.args.copy()
                new_args["transformed"] = True
                new_args["original_tool"] = invocation.tool_name
                return new_args

            async def on_success(self, invocation: ToolInvocation, result: object) -> object:
                return result

            async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
                pass

        invoker = ArgTransformer()
        invocation = ToolInvocation(tool_name="test", args={"arg1": "val1"})
        result = await invoker.transform_args(invocation)

        assert result == {
            "arg1": "val1",
            "transformed": True,
            "original_tool": "test",
        }

    @pytest.mark.asyncio
    async def test_custom_invoker_on_success_transforms_result(self):
        """Test custom invoker that transforms success result."""

        class ResultTransformer(ToolInvoker):
            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                return True

            async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
                return invocation.args

            async def on_success(self, invocation: ToolInvocation, result: object) -> object:
                return {"result": result, "tool": invocation.tool_name}

            async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
                pass

        invoker = ResultTransformer()
        invocation = ToolInvocation(tool_name="test", args={})
        original_result = {"output": "data"}
        result = await invoker.on_success(invocation, original_result)

        assert result == {"result": original_result, "tool": "test"}

    @pytest.mark.asyncio
    async def test_custom_invoker_on_error_logs_error(self):
        """Test custom invoker that logs errors."""

        class ErrorLogger(ToolInvoker):
            def __init__(self):
                self.errors = []

            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                return True

            async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
                return invocation.args

            async def on_success(self, invocation: ToolInvocation, result: object) -> object:
                return result

            async def on_error(self, invocation: ToolInvocation, error: Exception) -> None:
                self.errors.append((invocation.tool_name, str(error)))

        invoker = ErrorLogger()
        invocation = ToolInvocation(tool_name="failing_tool", args={})
        error = Exception("Tool failed")

        await invoker.on_error(invocation, error)

        assert len(invoker.errors) == 1
        assert invoker.errors[0] == ("failing_tool", "Tool failed")


class TestToolInvokerABC:
    """Test that ToolInvoker ABC cannot be instantiated directly."""

    def test_tool_invoker_cannot_be_instantiated(self):
        """Test that abstract ToolInvoker cannot be instantiated."""
        with pytest.raises(TypeError):
            ToolInvoker()

    def test_custom_invoker_must_implement_all_methods(self):
        """Test that custom invoker must implement all abstract methods."""

        class IncompleteInvoker(ToolInvoker):
            async def should_invoke(self, invocation: ToolInvocation) -> bool:
                return True

            async def transform_args(self, invocation: ToolInvocation) -> dict[str, object]:
                return invocation.args

            async def on_success(self, invocation: ToolInvocation, result: object) -> object:
                return result

        with pytest.raises(TypeError):
            IncompleteInvoker()
