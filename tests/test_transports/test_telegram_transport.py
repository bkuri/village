from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from telegram.error import InvalidToken, TelegramError

from village.chat.transports.telegram import TelegramTransport
from village.config import TelegramConfig


def _make_config() -> TelegramConfig:
    return TelegramConfig(bot_token_env="VILLAGE_TELEGRAM_BOT_TOKEN")


def _make_transport(
    config: TelegramConfig | None = None,
    summarize_fn: Callable[[str], Awaitable[str]] | None = None,
) -> TelegramTransport:
    if config is None:
        config = _make_config()
    return TelegramTransport(config=config, summarize_fn=summarize_fn)


class TestStart:
    @pytest.mark.asyncio
    async def test_missing_bot_token_raises_click_exception(self) -> None:
        transport = _make_transport()
        with patch.dict("os.environ", {}, clear=True), pytest.raises(click.ClickException, match="bot token not found"):
            await transport.start()

    @pytest.mark.asyncio
    async def test_empty_bot_token_raises_click_exception(self) -> None:
        transport = _make_transport()
        with (
            patch.dict("os.environ", {"VILLAGE_TELEGRAM_BOT_TOKEN": ""}, clear=False),
            pytest.raises(click.ClickException, match="bot token not found"),
        ):
            await transport.start()

    @pytest.mark.asyncio
    async def test_invalid_bot_token_raises_click_exception(self) -> None:
        transport = _make_transport()
        with (
            patch.dict("os.environ", {"VILLAGE_TELEGRAM_BOT_TOKEN": "invalid-token-12345"}),
            patch("village.chat.transports.telegram.Bot") as mock_bot_cls,
        ):
            mock_bot = AsyncMock()
            mock_bot.get_me.side_effect = InvalidToken("Invalid token")
            mock_bot_cls.return_value = mock_bot
            with pytest.raises(click.ClickException, match="Invalid Telegram bot token"):
                await transport.start()

    @pytest.mark.asyncio
    async def test_valid_token_initializes_transport(self) -> None:
        transport = _make_transport()
        with (
            patch.dict("os.environ", {"VILLAGE_TELEGRAM_BOT_TOKEN": "valid-token"}),
            patch("village.chat.transports.telegram.ApplicationBuilder") as mock_app_builder,
            patch("village.chat.transports.telegram.Bot") as mock_bot_cls,
        ):
            mock_bot = AsyncMock()
            mock_me = MagicMock()
            mock_me.username = "test_bot"
            mock_bot.get_me = AsyncMock(return_value=mock_me)
            mock_bot.id = 42
            mock_bot_cls.return_value = mock_bot

            mock_app = AsyncMock()
            mock_app.updater = AsyncMock()
            mock_builder = MagicMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_app
            mock_app_builder.return_value = mock_builder

            await transport.start()
            assert transport._running is True
            assert transport._bot is mock_bot


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self) -> None:
        transport = _make_transport()
        transport._running = True
        transport._application = None
        await transport.stop()
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_stop_shuts_down_application(self) -> None:
        transport = _make_transport()
        transport._running = True
        mock_updater = AsyncMock()
        mock_app = MagicMock()
        mock_app.updater = mock_updater
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        transport._application = mock_app

        await transport.stop()
        assert transport._running is False
        mock_updater.stop.assert_awaited_once()
        mock_app.stop.assert_awaited_once()
        mock_app.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_without_updater(self) -> None:
        transport = _make_transport()
        transport._running = True
        mock_app = MagicMock()
        mock_app.updater = None
        mock_app.stop = AsyncMock()
        mock_app.shutdown = AsyncMock()
        transport._application = mock_app

        await transport.stop()
        assert transport._running is False
        mock_app.stop.assert_awaited_once()
        mock_app.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_without_application(self) -> None:
        transport = _make_transport()
        transport._running = True
        transport._application = None
        await transport.stop()
        assert transport._running is False


class TestSend:
    @pytest.mark.asyncio
    async def test_send_message_via_bot(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        transport._bot = mock_bot
        transport._chat_id = 12345

        await transport.send("Hello!")
        mock_bot.send_message.assert_called_once_with(chat_id=12345, text="Hello!")

    @pytest.mark.asyncio
    async def test_send_without_bot_does_nothing(self) -> None:
        transport = _make_transport()
        transport._bot = None
        transport._chat_id = 12345
        await transport.send("Hello!")
        assert True

    @pytest.mark.asyncio
    async def test_send_without_chat_id_does_nothing(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        transport._bot = mock_bot
        transport._chat_id = None
        await transport.send("Hello!")
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_handles_telegram_error(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = TelegramError("Network error")
        transport._bot = mock_bot
        transport._chat_id = 12345

        await transport.send("Hello!")
        assert True


class TestReceive:
    @pytest.mark.asyncio
    async def test_receive_returns_message_from_queue(self) -> None:
        transport = _make_transport()
        transport._running = True
        await transport._message_queue.put("test message")

        result = await transport.receive()
        assert result == "test message"

    @pytest.mark.asyncio
    async def test_receive_returns_exit_when_not_running(self) -> None:
        transport = _make_transport()
        transport._running = False
        result = await transport.receive()
        assert result == "/exit"

    @pytest.mark.asyncio
    async def test_receive_returns_multiple_messages_in_order(self) -> None:
        transport = _make_transport()
        transport._running = True
        await transport._message_queue.put("first")
        await transport._message_queue.put("second")

        assert await transport.receive() == "first"
        assert await transport.receive() == "second"


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_handle_message_puts_text_in_queue(self) -> None:
        transport = _make_transport()
        transport._running = True

        mock_update = MagicMock()
        mock_update.message.text = "hello"
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_message(mock_update, mock_context)
        result = await transport._message_queue.get()
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_handle_message_initializes_state_manager_on_first_message(self) -> None:
        transport = _make_transport()
        transport._running = True
        mock_bot = AsyncMock()
        transport._bot = mock_bot

        mock_update = MagicMock()
        mock_update.message.text = "hello"
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_message(mock_update, mock_context)
        assert transport._chat_id == 12345
        assert transport._state_manager is not None

    @pytest.mark.asyncio
    async def test_handle_message_without_message_ignores(self) -> None:
        transport = _make_transport()
        transport._running = True
        mock_update = MagicMock()
        mock_update.message = None
        mock_context = MagicMock()

        await transport._handle_message(mock_update, mock_context)
        assert transport._message_queue.empty()

    @pytest.mark.asyncio
    async def test_handle_message_without_chat_ignores(self) -> None:
        transport = _make_transport()
        transport._running = True
        mock_update = MagicMock()
        mock_update.message.text = "hello"
        mock_update.effective_chat = None
        mock_context = MagicMock()

        await transport._handle_message(mock_update, mock_context)
        assert transport._message_queue.empty()


class TestHandleCommand:
    @pytest.mark.asyncio
    async def test_exit_command_stops_bot(self) -> None:
        transport = _make_transport()
        transport._running = True

        mock_update = MagicMock()
        mock_update.message.text = "/exit"
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_command(mock_update, mock_context)
        assert transport._running is False
        result = await transport._message_queue.get()
        assert result == "/exit"

    @pytest.mark.asyncio
    async def test_other_commands_are_ignored(self) -> None:
        transport = _make_transport()
        transport._running = True

        mock_update = MagicMock()
        mock_update.message.text = "/start"
        mock_context = MagicMock()

        await transport._handle_command(mock_update, mock_context)
        assert transport._running is True
        assert transport._message_queue.empty()

    @pytest.mark.asyncio
    async def test_exit_command_case_insensitive(self) -> None:
        transport = _make_transport()
        transport._running = True

        mock_update = MagicMock()
        mock_update.message.text = "/EXIT"
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_command(mock_update, mock_context)
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_command_without_message_ignores(self) -> None:
        transport = _make_transport()
        transport._running = True

        mock_update = MagicMock()
        mock_update.message = None
        mock_context = MagicMock()

        await transport._handle_command(mock_update, mock_context)
        assert transport._running is True


class TestHandleNonText:
    @pytest.mark.asyncio
    async def test_non_text_message_gets_rejection(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        transport._bot = mock_bot

        mock_update = MagicMock()
        mock_update.message.text = None
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_non_text(mock_update, mock_context)
        mock_bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="Text only, please.",
        )

    @pytest.mark.asyncio
    async def test_non_text_without_bot_ignores(self) -> None:
        transport = _make_transport()
        transport._bot = None

        mock_update = MagicMock()
        mock_update.message.text = None
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_non_text(mock_update, mock_context)
        assert True

    @pytest.mark.asyncio
    async def test_non_text_handles_telegram_error(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = TelegramError("Send failed")
        transport._bot = mock_bot

        mock_update = MagicMock()
        mock_update.message.text = None
        mock_update.effective_chat.id = 12345
        mock_context = MagicMock()

        await transport._handle_non_text(mock_update, mock_context)
        assert True


class TestName:
    def test_name_returns_telegram(self) -> None:
        transport = _make_transport()
        assert transport.name == "telegram"


class TestRoute:
    @pytest.mark.asyncio
    async def test_route_sends_routing_message(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        transport._bot = mock_bot
        transport._chat_id = 12345

        await transport.route("builder")
        mock_bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="Routing to builder.",
        )

    @pytest.mark.asyncio
    async def test_route_with_context(self) -> None:
        transport = _make_transport()
        mock_bot = AsyncMock()
        transport._bot = mock_bot
        transport._chat_id = 12345

        await transport.route("planner", context="design auth")
        mock_bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="Routing to planner.\nContext: design auth",
        )
