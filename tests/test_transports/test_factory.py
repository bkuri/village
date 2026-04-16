from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from village.chat.transports import AsyncTransport, create_transport
from village.chat.transports.cli import CLITransport
from village.chat.transports.telegram import TelegramTransport
from village.config import TelegramConfig


def test_create_cli_transport() -> None:
    transport = create_transport("cli")
    assert isinstance(transport, CLITransport)
    assert isinstance(transport, AsyncTransport)


def test_create_telegram_transport() -> None:
    mock_config = MagicMock()
    mock_config.telegram = TelegramConfig()
    transport = create_transport("telegram", config=mock_config)
    assert isinstance(transport, TelegramTransport)
    assert isinstance(transport, AsyncTransport)


def test_create_telegram_transport_with_summarize_fn() -> None:
    mock_config = MagicMock()
    mock_config.telegram = TelegramConfig()
    summarize_fn = AsyncMock(return_value="summary")
    transport = create_transport(
        "telegram",
        config=mock_config,
        summarize_fn=summarize_fn,
    )
    assert isinstance(transport, TelegramTransport)


def test_unknown_transport_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown transport: slack"):
        create_transport("slack")


def test_unknown_transport_with_config_still_raises() -> None:
    mock_config = MagicMock()
    with pytest.raises(ValueError, match="Unknown transport: discord"):
        create_transport("discord", config=mock_config)


def test_create_transport_empty_name_raises() -> None:
    with pytest.raises(ValueError, match="Unknown transport: "):
        create_transport("")
