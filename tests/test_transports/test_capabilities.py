from __future__ import annotations

import pytest

from village.chat.transports import TransportCapabilities
from village.chat.transports.cli import CLITransport
from village.chat.transports.telegram import TelegramTransport
from village.config import TelegramConfig


def test_default_capabilities_all_false() -> None:
    caps = TransportCapabilities()
    assert caps.streaming is False
    assert caps.files is False
    assert caps.terminal is False
    assert caps.markdown is False
    assert caps.menus is False
    assert caps.persistence is False


def test_cli_capabilities() -> None:
    transport = CLITransport()
    caps = transport.capabilities
    assert caps.streaming is True
    assert caps.files is True
    assert caps.terminal is True
    assert caps.markdown is False
    assert caps.menus is False
    assert caps.persistence is False


def test_telegram_capabilities() -> None:
    config = TelegramConfig()
    transport = TelegramTransport(config)
    caps = transport.capabilities
    assert caps.streaming is False
    assert caps.files is False
    assert caps.terminal is False
    assert caps.markdown is True
    assert caps.menus is True
    assert caps.persistence is True


def test_capabilities_frozen() -> None:
    caps = TransportCapabilities()
    with pytest.raises(AttributeError):
        caps.streaming = True  # type: ignore[misc]

    with pytest.raises(AttributeError):
        caps.markdown = True  # type: ignore[misc]


def test_capabilities_frozen_with_values() -> None:
    caps = TransportCapabilities(streaming=True, markdown=True)
    with pytest.raises(AttributeError):
        caps.streaming = False  # type: ignore[misc]

    with pytest.raises(AttributeError):
        caps.files = True  # type: ignore[misc]


def test_capabilities_partial_override() -> None:
    caps = TransportCapabilities(streaming=True)
    assert caps.streaming is True
    assert caps.files is False
    assert caps.markdown is False
    assert caps.menus is False
    assert caps.persistence is False
    assert caps.terminal is False


def test_capabilities_all_true() -> None:
    caps = TransportCapabilities(
        streaming=True,
        files=True,
        terminal=True,
        markdown=True,
        menus=True,
        persistence=True,
    )
    assert caps.streaming is True
    assert caps.files is True
    assert caps.terminal is True
    assert caps.markdown is True
    assert caps.menus is True
    assert caps.persistence is True


def test_capabilities_equality() -> None:
    caps_a = TransportCapabilities(streaming=True, files=True)
    caps_b = TransportCapabilities(streaming=True, files=True)
    caps_c = TransportCapabilities(streaming=True, files=False)
    assert caps_a == caps_b
    assert caps_a != caps_c
