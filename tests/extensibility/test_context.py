"""Test ChatContext ABC and DefaultChatContext."""

import pytest

from village.extensibility.context import ChatContext, DefaultChatContext, SessionContext


class TestSessionContext:
    """Test SessionContext dataclass."""

    def test_session_context_initialization(self):
        """Test SessionContext initialization with required fields."""
        context = SessionContext(session_id="test-session")
        assert context.session_id == "test-session"
        assert context.user_data == {}
        assert context.metadata == {}

    def test_session_context_with_user_data(self):
        """Test SessionContext initialization with user_data."""
        user_data = {"key": "value", "count": 42}
        context = SessionContext(session_id="test", user_data=user_data)
        assert context.user_data == user_data

    def test_session_context_with_metadata(self):
        """Test SessionContext initialization with metadata."""
        metadata = {"created_at": "2024-01-01", "user": "test"}
        context = SessionContext(session_id="test", metadata=metadata)
        assert context.metadata == metadata

    def test_session_context_all_fields(self):
        """Test SessionContext with all fields."""
        user_data = {"key": "value"}
        metadata = {"meta": "data"}
        context = SessionContext(
            session_id="test",
            user_data=user_data,
            metadata=metadata,
        )
        assert context.session_id == "test"
        assert context.user_data == user_data
        assert context.metadata == metadata

    def test_session_context_get_existing_key(self):
        """Test SessionContext.get with existing key."""
        context = SessionContext(session_id="test")
        context.set("key1", "value1")
        result = context.get("key1")
        assert result == "value1"

    def test_session_context_get_nonexistent_key(self):
        """Test SessionContext.get with nonexistent key."""
        context = SessionContext(session_id="test")
        result = context.get("nonexistent")
        assert result is None

    def test_session_context_get_with_default(self):
        """Test SessionContext.get with default value."""
        context = SessionContext(session_id="test")
        result = context.get("nonexistent", "default")
        assert result == "default"

    def test_session_context_get_with_default_existing_key(self):
        """Test SessionContext.get with default value for existing key."""
        context = SessionContext(session_id="test")
        context.set("key", "value")
        result = context.get("key", "default")
        assert result == "value"

    def test_session_context_set_new_key(self):
        """Test SessionContext.set with new key."""
        context = SessionContext(session_id="test")
        context.set("new_key", "new_value")
        assert context.get("new_key") == "new_value"

    def test_session_context_set_existing_key(self):
        """Test SessionContext.set overwrites existing key."""
        context = SessionContext(session_id="test")
        context.set("key", "value1")
        context.set("key", "value2")
        assert context.get("key") == "value2"

    def test_session_context_set_various_types(self):
        """Test SessionContext.set with various value types."""
        context = SessionContext(session_id="test")

        context.set("string", "value")
        context.set("int", 42)
        context.set("float", 3.14)
        context.set("bool", True)
        context.set("list", [1, 2, 3])
        context.set("dict", {"nested": "value"})
        context.set("none", None)

        assert context.get("string") == "value"
        assert context.get("int") == 42
        assert context.get("float") == 3.14
        assert context.get("bool") is True
        assert context.get("list") == [1, 2, 3]
        assert context.get("dict") == {"nested": "value"}
        assert context.get("none") is None

    def test_session_context_multiple_sessions_independent(self):
        """Test that different SessionContext instances are independent."""
        context1 = SessionContext(session_id="session-1")
        context2 = SessionContext(session_id="session-2")

        context1.set("key", "value1")
        context2.set("key", "value2")

        assert context1.get("key") == "value1"
        assert context2.get("key") == "value2"


class TestDefaultChatContext:
    """Test DefaultChatContext behavior."""

    @pytest.mark.asyncio
    async def test_load_context_returns_empty_session_context(self):
        """Test that load_context returns empty SessionContext."""
        chat_context = DefaultChatContext()
        result = await chat_context.load_context("test-session-id")

        assert isinstance(result, SessionContext)
        assert result.session_id == "test-session-id"
        assert result.user_data == {}
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_load_context_with_different_session_ids(self):
        """Test load_context with different session IDs."""
        chat_context = DefaultChatContext()

        context1 = await chat_context.load_context("session-1")
        context2 = await chat_context.load_context("session-2")

        assert context1.session_id == "session-1"
        assert context2.session_id == "session-2"
        assert context1 is not context2

    @pytest.mark.asyncio
    async def test_load_context_returns_fresh_instances(self):
        """Test that load_context returns fresh instances each time."""
        chat_context = DefaultChatContext()

        context1 = await chat_context.load_context("session")
        context1.set("key", "value")

        context2 = await chat_context.load_context("session")

        assert context2.get("key") is None

    @pytest.mark.asyncio
    async def test_save_context_does_nothing(self):
        """Test that save_context does nothing."""
        chat_context = DefaultChatContext()
        context = SessionContext(
            session_id="test",
            user_data={"key": "value"},
        )

        result = await chat_context.save_context(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_save_context_with_large_data(self):
        """Test save_context with large data structure."""
        chat_context = DefaultChatContext()
        large_data = {"key_" + str(i): "value_" + str(i) for i in range(1000)}
        context = SessionContext(session_id="test", user_data=large_data)

        result = await chat_context.save_context(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_context_returns_unchanged(self):
        """Test that enrich_context returns context unchanged."""
        chat_context = DefaultChatContext()
        context = SessionContext(
            session_id="test",
            user_data={"key": "value"},
            metadata={"meta": "data"},
        )

        result = await chat_context.enrich_context(context)

        assert result is context
        assert result.session_id == "test"
        assert result.user_data == {"key": "value"}
        assert result.metadata == {"meta": "data"}

    @pytest.mark.asyncio
    async def test_enrich_context_with_empty_context(self):
        """Test enrich_context with empty SessionContext."""
        chat_context = DefaultChatContext()
        context = SessionContext(session_id="test")

        result = await chat_context.enrich_context(context)

        assert result is context
        assert result.user_data == {}
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_enrich_context_returns_same_instance(self):
        """Test that enrich_context returns the same instance."""
        chat_context = DefaultChatContext()
        context = SessionContext(session_id="test")

        result = await chat_context.enrich_context(context)

        assert result is context


class TestCustomChatContext:
    """Test custom ChatContext implementations."""

    @pytest.mark.asyncio
    async def test_custom_context_loads_data(self):
        """Test custom context that loads data."""

        class LoadingChatContext(ChatContext):
            async def load_context(self, session_id: str) -> SessionContext:
                return SessionContext(
                    session_id=session_id,
                    user_data={"loaded": True, "session": session_id},
                )

            async def save_context(self, context: SessionContext) -> None:
                pass

            async def enrich_context(self, context: SessionContext) -> SessionContext:
                return context

        context = LoadingChatContext()
        result = await context.load_context("test-session")

        assert result.session_id == "test-session"
        assert result.user_data == {"loaded": True, "session": "test-session"}

    @pytest.mark.asyncio
    async def test_custom_context_saves_data(self):
        """Test custom context that saves data."""

        class SavingChatContext(ChatContext):
            def __init__(self):
                self.saved_contexts = []

            async def load_context(self, session_id: str) -> SessionContext:
                return SessionContext(session_id=session_id)

            async def save_context(self, context: SessionContext) -> None:
                self.saved_contexts.append(context)

            async def enrich_context(self, context: SessionContext) -> SessionContext:
                return context

        context = SavingChatContext()
        session_context = SessionContext(
            session_id="test",
            user_data={"key": "value"},
        )

        await context.save_context(session_context)

        assert len(context.saved_contexts) == 1
        assert context.saved_contexts[0].session_id == "test"

    @pytest.mark.asyncio
    async def test_custom_context_enriches_data(self):
        """Test custom context that enriches data."""

        class EnrichingChatContext(ChatContext):
            async def load_context(self, session_id: str) -> SessionContext:
                return SessionContext(session_id=session_id)

            async def save_context(self, context: SessionContext) -> None:
                pass

            async def enrich_context(self, context: SessionContext) -> SessionContext:
                enriched = SessionContext(
                    session_id=context.session_id,
                    user_data=context.user_data.copy(),
                    metadata=context.metadata.copy(),
                )
                enriched.set("enriched", True)
                enriched.metadata["enriched_at"] = "2024-01-01"
                return enriched

        context = EnrichingChatContext()
        original = SessionContext(session_id="test")

        result = await context.enrich_context(original)

        assert result.session_id == "test"
        assert result.get("enriched") is True
        assert result.metadata["enriched_at"] == "2024-01-01"
        assert original.get("enriched") is None

    @pytest.mark.asyncio
    async def test_custom_context_with_full_workflow(self):
        """Test custom context with full load/enrich/save workflow."""

        class FullChatContext(ChatContext):
            def __init__(self):
                self.storage = {}

            async def load_context(self, session_id: str) -> SessionContext:
                if session_id in self.storage:
                    return self.storage[session_id]
                return SessionContext(session_id=session_id)

            async def save_context(self, context: SessionContext) -> None:
                self.storage[context.session_id] = context

            async def enrich_context(self, context: SessionContext) -> SessionContext:
                if not context.get("enriched"):
                    context.set("enriched", True)
                return context

        context = FullChatContext()

        loaded = await context.load_context("session-1")
        loaded.set("user_input", "test")

        enriched = await context.enrich_context(loaded)
        await context.save_context(enriched)

        reloaded = await context.load_context("session-1")

        assert reloaded.get("user_input") == "test"
        assert reloaded.get("enriched") is True


class TestChatContextABC:
    """Test that ChatContext ABC cannot be instantiated directly."""

    def test_chat_context_cannot_be_instantiated(self):
        """Test that abstract ChatContext cannot be instantiated."""
        with pytest.raises(TypeError):
            ChatContext()

    def test_custom_context_must_implement_all_methods(self):
        """Test that custom context must implement all abstract methods."""

        class IncompleteContext(ChatContext):
            async def load_context(self, session_id: str) -> SessionContext:
                return SessionContext(session_id=session_id)

            async def save_context(self, context: SessionContext) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteContext()
