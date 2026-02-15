"""Test ChatProcessor ABC and DefaultChatProcessor."""

import pytest

from village.extensibility.processors import ChatProcessor, DefaultChatProcessor, ProcessingResult


class TestProcessingResult:
    """Test ProcessingResult dataclass."""

    def test_processing_result_initialization(self):
        """Test ProcessingResult initialization with content only."""
        result = ProcessingResult(content="test content")
        assert result.content == "test content"
        assert result.metadata == {}

    def test_processing_result_with_metadata(self):
        """Test ProcessingResult initialization with metadata."""
        metadata = {"key": "value", "count": 42}
        result = ProcessingResult(content="test", metadata=metadata)
        assert result.content == "test"
        assert result.metadata == metadata

    def test_processing_result_none_metadata_becomes_empty_dict(self):
        """Test that None metadata becomes empty dict via post_init."""
        result = ProcessingResult(content="test", metadata=None)
        assert result.metadata == {}

    def test_processing_result_metadata_mutation(self):
        """Test that metadata dict can be mutated."""
        result = ProcessingResult(content="test")
        result.metadata["new_key"] = "new_value"
        assert result.metadata == {"new_key": "new_value"}


class TestDefaultChatProcessor:
    """Test DefaultChatProcessor behavior."""

    @pytest.mark.asyncio
    async def test_pre_process_returns_input_unchanged(self):
        """Test that pre_process returns input unchanged."""
        processor = DefaultChatProcessor()
        user_input = "Hello, world!"
        result = await processor.pre_process(user_input)
        assert result == user_input
        assert result is user_input

    @pytest.mark.asyncio
    async def test_pre_process_with_empty_string(self):
        """Test pre_process with empty string."""
        processor = DefaultChatProcessor()
        result = await processor.pre_process("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_pre_process_with_multiline(self):
        """Test pre_process with multiline input."""
        processor = DefaultChatProcessor()
        user_input = "Line 1\nLine 2\nLine 3"
        result = await processor.pre_process(user_input)
        assert result == user_input

    @pytest.mark.asyncio
    async def test_pre_process_with_special_chars(self):
        """Test pre_process with special characters."""
        processor = DefaultChatProcessor()
        user_input = "Test with 🎉 emojis & special chars!"
        result = await processor.pre_process(user_input)
        assert result == user_input

    @pytest.mark.asyncio
    async def test_post_process_returns_response_unchanged(self):
        """Test that post_process returns response unchanged."""
        processor = DefaultChatProcessor()
        response = "This is the LLM response."
        result = await processor.post_process(response)
        assert result == response
        assert result is response

    @pytest.mark.asyncio
    async def test_post_process_with_empty_string(self):
        """Test post_process with empty string."""
        processor = DefaultChatProcessor()
        result = await processor.post_process("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_post_process_with_multiline(self):
        """Test post_process with multiline response."""
        processor = DefaultChatProcessor()
        response = "Response line 1\nResponse line 2"
        result = await processor.post_process(response)
        assert result == response

    @pytest.mark.asyncio
    async def test_post_process_with_special_chars(self):
        """Test post_process with special characters."""
        processor = DefaultChatProcessor()
        response = "Response with <html> tags & code ```"
        result = await processor.post_process(response)
        assert result == response


class TestCustomChatProcessor:
    """Test custom ChatProcessor implementations."""

    @pytest.mark.asyncio
    async def test_custom_processor_pre_process(self):
        """Test that custom processor can implement pre_process."""

        class UppercaseProcessor(ChatProcessor):
            async def pre_process(self, user_input: str) -> str:
                return user_input.upper()

            async def post_process(self, response: str) -> str:
                return response

        processor = UppercaseProcessor()
        result = await processor.pre_process("hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_custom_processor_post_process(self):
        """Test that custom processor can implement post_process."""

        class LowercaseProcessor(ChatProcessor):
            async def pre_process(self, user_input: str) -> str:
                return user_input

            async def post_process(self, response: str) -> str:
                return response.lower()

        processor = LowercaseProcessor()
        result = await processor.post_process("HELLO")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_custom_processor_both_methods(self):
        """Test custom processor implementing both methods."""

        class EchoProcessor(ChatProcessor):
            async def pre_process(self, user_input: str) -> str:
                return f"[PRE] {user_input}"

            async def post_process(self, response: str) -> str:
                return f"[POST] {response}"

        processor = EchoProcessor()
        pre_result = await processor.pre_process("test")
        post_result = await processor.post_process("response")
        assert pre_result == "[PRE] test"
        assert post_result == "[POST] response"

    @pytest.mark.asyncio
    async def test_custom_processor_with_side_effects(self):
        """Test custom processor can have side effects."""

        class TrackingProcessor(ChatProcessor):
            def __init__(self):
                self.pre_calls = []
                self.post_calls = []

            async def pre_process(self, user_input: str) -> str:
                self.pre_calls.append(user_input)
                return user_input

            async def post_process(self, response: str) -> str:
                self.post_calls.append(response)
                return response

        processor = TrackingProcessor()
        await processor.pre_process("input1")
        await processor.post_process("response1")
        await processor.pre_process("input2")
        await processor.post_process("response2")

        assert processor.pre_calls == ["input1", "input2"]
        assert processor.post_calls == ["response1", "response2"]


class TestChatProcessorABC:
    """Test that ChatProcessor ABC cannot be instantiated directly."""

    def test_chat_processor_cannot_be_instantiated(self):
        """Test that abstract ChatProcessor cannot be instantiated."""
        with pytest.raises(TypeError):
            ChatProcessor()

    def test_custom_processor_must_implement_all_methods(self):
        """Test that custom processor must implement all abstract methods."""

        class IncompleteProcessor(ChatProcessor):
            async def pre_process(self, user_input: str) -> str:
                return user_input

        with pytest.raises(TypeError):
            IncompleteProcessor()
