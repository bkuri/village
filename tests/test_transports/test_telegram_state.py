from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from village.chat.transports.telegram import (
    SessionPhase,
    TelegramStateManager,
)
from village.config import TelegramConfig


def _make_config(
    milestone_interval: int = 50,
    max_context_messages: int = 10,
) -> TelegramConfig:
    return TelegramConfig(
        bot_token_env="TEST_TOKEN",
        milestone_interval=milestone_interval,
        max_context_messages=max_context_messages,
    )


def _make_manager(
    config: TelegramConfig | None = None,
    summarize_fn: AsyncMock | None = None,
) -> tuple[TelegramStateManager, MagicMock]:
    if config is None:
        config = _make_config()
    bot = MagicMock()
    manager = TelegramStateManager(
        bot=bot,
        chat_id=12345,
        config=config,
        summarize_fn=summarize_fn,
    )
    return manager, bot


VALID_PINNED_MESSAGE = """[VILLAGE SESSION]
Counter: 7/50

Milestone:
User asked about auth system. We discussed JWT tokens."""


class TestParseState:
    def test_valid_pinned_message_parses_correctly(self) -> None:
        manager, _ = _make_manager()
        state = manager._parse_state(VALID_PINNED_MESSAGE)
        assert state.counter == 7
        assert state.interval == 50
        assert state.milestone == "User asked about auth system. We discussed JWT tokens."

    def test_missing_counter_defaults_to_zero(self) -> None:
        manager, _ = _make_manager()
        message = "[VILLAGE SESSION]\nMilestone:\nsome milestone text"
        state = manager._parse_state(message)
        assert state.counter == 0
        assert state.interval == 50

    def test_missing_milestone_defaults_to_empty(self) -> None:
        manager, _ = _make_manager()
        message = "[VILLAGE SESSION]\nCounter: 10/50"
        state = manager._parse_state(message)
        assert state.counter == 10
        assert state.interval == 50
        assert state.milestone == ""

    def test_emoji_in_milestone_text_does_not_break_parsing(self) -> None:
        manager, _ = _make_manager()
        message = """[VILLAGE SESSION]
Counter: 3/50

Milestone:
User wants 🚀 fast auth with 🔐 security and ✅ reliability."""
        state = manager._parse_state(message)
        assert state.counter == 3
        assert "🚀" in state.milestone
        assert "🔐" in state.milestone
        assert "✅" in state.milestone

    def test_very_long_milestone_text_parses_correctly(self) -> None:
        manager, _ = _make_manager()
        long_milestone = "x" * 1500
        message = f"""[VILLAGE SESSION]
Counter: 25/100

Milestone:
{long_milestone}"""
        state = manager._parse_state(message)
        assert state.counter == 25
        assert state.interval == 100
        assert state.milestone == long_milestone

    def test_empty_message_body_returns_defaults(self) -> None:
        manager, _ = _make_manager()
        state = manager._parse_state("")
        assert state.counter == 0
        assert state.interval == 50
        assert state.milestone == ""

    def test_random_non_village_message_returns_defaults(self) -> None:
        manager, _ = _make_manager()
        message = "This is just a regular chat message, nothing special here."
        state = manager._parse_state(message)
        assert state.counter == 0
        assert state.interval == 50
        assert state.milestone == ""

    def test_partial_counter_only_counter_value(self) -> None:
        manager, _ = _make_manager()
        message = "[VILLAGE SESSION]\nCounter: 42/"
        state = manager._parse_state(message)
        assert state.counter == 0

    def test_counter_with_different_interval(self) -> None:
        manager, _ = _make_manager()
        message = "[VILLAGE SESSION]\nCounter: 15/100"
        state = manager._parse_state(message)
        assert state.counter == 15
        assert state.interval == 100


class TestBuildStateMessage:
    def test_builds_message_with_counter_only(self) -> None:
        manager, _ = _make_manager()
        result = manager._build_state_message(5, 50, "")
        assert "[VILLAGE SESSION]" in result
        assert "Counter: 5/50" in result
        assert "Milestone:" not in result

    def test_builds_message_with_milestone(self) -> None:
        manager, _ = _make_manager()
        result = manager._build_state_message(10, 50, "Built auth system")
        assert "[VILLAGE SESSION]" in result
        assert "Counter: 10/50" in result
        assert "Milestone:\nBuilt auth system" in result

    def test_builds_message_with_zero_counter(self) -> None:
        manager, _ = _make_manager()
        result = manager._build_state_message(0, 50, "")
        assert "Counter: 0/50" in result

    def test_builds_message_with_multiline_milestone(self) -> None:
        manager, _ = _make_manager()
        result = manager._build_state_message(5, 50, "Line one\nLine two\nLine three")
        assert "Milestone:\nLine one\nLine two\nLine three" in result

    def test_round_trip_parse_and_build(self) -> None:
        manager, _ = _make_manager()
        original = manager._build_state_message(7, 50, "Discussed auth system design")
        parsed = manager._parse_state(original)
        assert parsed.counter == 7
        assert parsed.interval == 50
        assert parsed.milestone == "Discussed auth system design"


class TestTrackMessage:
    def test_tracks_single_message(self) -> None:
        manager, _ = _make_manager()
        manager.track_message("hello")
        assert manager._context_messages == ["hello"]

    def test_tracks_multiple_messages(self) -> None:
        manager, _ = _make_manager()
        manager.track_message("first")
        manager.track_message("second")
        manager.track_message("third")
        assert manager._context_messages == ["first", "second", "third"]

    def test_trims_to_max_context_messages(self) -> None:
        config = _make_config(max_context_messages=3)
        manager, _ = _make_manager(config=config)
        manager.track_message("a")
        manager.track_message("b")
        manager.track_message("c")
        manager.track_message("d")
        assert manager._context_messages == ["b", "c", "d"]

    def test_trims_exactly_at_boundary(self) -> None:
        config = _make_config(max_context_messages=2)
        manager, _ = _make_manager(config=config)
        manager.track_message("a")
        manager.track_message("b")
        assert manager._context_messages == ["a", "b"]


class TestTick:
    @pytest.mark.asyncio
    async def test_counter_increments(self) -> None:
        manager, bot = _make_manager()
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE

        await manager.tick()
        assert manager.counter == 1
        bot.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_milestone_compaction_triggers_at_interval_boundary(self) -> None:
        summarize_fn = AsyncMock(return_value="Summarized context")
        config = _make_config(milestone_interval=5)
        manager, bot = _make_manager(config=config, summarize_fn=summarize_fn)
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE
        manager._context_messages = ["msg1", "msg2"]

        for i in range(5):
            await manager.tick()

        assert manager.counter == 5
        assert manager.milestone == "Summarized context"
        assert manager.phase == SessionPhase.ACTIVE
        summarize_fn.assert_called_once()
        assert bot.edit_message_text.call_count == 6

    @pytest.mark.asyncio
    async def test_compaction_resets_context_messages(self) -> None:
        summarize_fn = AsyncMock(return_value="Summary")
        config = _make_config(milestone_interval=2)
        manager, bot = _make_manager(config=config, summarize_fn=summarize_fn)
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE
        manager._context_messages = ["msg1", "msg2"]

        await manager.tick()
        await manager.tick()

        assert manager._context_messages == []

    @pytest.mark.asyncio
    async def test_no_summarize_fn_milestone_stays_empty(self) -> None:
        config = _make_config(milestone_interval=2)
        manager, bot = _make_manager(config=config, summarize_fn=None)
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE
        manager._context_messages = ["first msg", "second msg"]

        await manager.tick()
        await manager.tick()

        assert manager.milestone == ""

    @pytest.mark.asyncio
    async def test_no_summarize_fn_context_messages_preserved(self) -> None:
        config = _make_config(milestone_interval=2)
        manager, bot = _make_manager(config=config, summarize_fn=None)
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE
        manager._context_messages = ["msg1", "msg2"]

        await manager.tick()
        await manager.tick()

        assert manager._context_messages == ["msg1", "msg2"]

    @pytest.mark.asyncio
    async def test_compaction_failure_falls_back_to_truncated_context(self) -> None:
        summarize_fn = AsyncMock(side_effect=RuntimeError("LLM down"))
        config = _make_config(milestone_interval=2)
        manager, bot = _make_manager(config=config, summarize_fn=summarize_fn)
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.ACTIVE
        manager._context_messages = ["short msg"]

        await manager.tick()
        await manager.tick()

        assert manager.milestone == "short msg"

    @pytest.mark.asyncio
    async def test_phase_transitions_new_to_active(self) -> None:
        manager, bot = _make_manager()
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.NEW

        await manager.tick()
        assert manager.phase == SessionPhase.ACTIVE

    @pytest.mark.asyncio
    async def test_phase_transitions_recover_to_active(self) -> None:
        manager, bot = _make_manager()
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = 99
        manager._phase = SessionPhase.RECOVER

        await manager.tick()
        assert manager.phase == SessionPhase.ACTIVE

    @pytest.mark.asyncio
    async def test_no_pinned_message_id_skips_update(self) -> None:
        manager, bot = _make_manager()
        bot.edit_message_text = AsyncMock()
        manager._pinned_message_id = None
        manager._phase = SessionPhase.ACTIVE

        await manager.tick()
        assert manager.counter == 1
        bot.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_with_existing_pinned_message() -> None:
    manager, bot = _make_manager()
    mock_chat = MagicMock()
    mock_pinned = MagicMock()
    mock_pinned.from_user.id = bot.id
    mock_pinned.text = VALID_PINNED_MESSAGE
    mock_pinned.message_id = 42
    mock_chat.pinned_message = mock_pinned
    bot.get_chat = AsyncMock(return_value=mock_chat)

    await manager.initialize()
    assert manager.counter == 7
    assert manager.milestone == "User asked about auth system. We discussed JWT tokens."
    assert manager.phase == SessionPhase.RECOVER
    assert manager._pinned_message_id == 42


@pytest.mark.asyncio
async def test_initialize_without_pinned_message_creates_new() -> None:
    manager, bot = _make_manager()
    mock_chat = MagicMock()
    mock_chat.pinned_message = None
    bot.get_chat = AsyncMock(return_value=mock_chat)
    sent = MagicMock()
    sent.message_id = 77
    bot.send_message = AsyncMock(return_value=sent)
    bot.pin_chat_message = AsyncMock()

    await manager.initialize()
    assert manager.phase == SessionPhase.NEW
    assert manager._pinned_message_id == 77
    bot.send_message.assert_called_once()
    bot.pin_chat_message.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_ignores_non_village_pinned_message() -> None:
    manager, bot = _make_manager()
    mock_chat = MagicMock()
    mock_pinned = MagicMock()
    mock_pinned.from_user.id = bot.id
    mock_pinned.text = "Just a regular pinned message"
    mock_pinned.message_id = 42
    mock_chat.pinned_message = mock_pinned
    bot.get_chat = AsyncMock(return_value=mock_chat)
    sent = MagicMock()
    sent.message_id = 88
    bot.send_message = AsyncMock(return_value=sent)
    bot.pin_chat_message = AsyncMock()

    await manager.initialize()
    assert manager.phase == SessionPhase.NEW
    assert manager._pinned_message_id == 88


@pytest.mark.asyncio
async def test_initialize_handles_telegram_error_gracefully() -> None:
    from telegram.error import TelegramError

    manager, bot = _make_manager()
    bot.get_chat = AsyncMock(side_effect=TelegramError("Network error"))
    sent = MagicMock()
    sent.message_id = 99
    bot.send_message = AsyncMock(return_value=sent)
    bot.pin_chat_message = AsyncMock()

    await manager.initialize()
    assert manager.phase == SessionPhase.NEW
    bot.send_message.assert_called_once()
