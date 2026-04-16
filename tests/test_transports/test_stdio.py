from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from village.chat.transports import create_transport, get_transport_names
from village.chat.transports.stdio import StdioTransport


def test_name_returns_stdio() -> None:
    transport = StdioTransport()
    assert transport.name == "stdio"


def test_capabilities() -> None:
    transport = StdioTransport()
    caps = transport.capabilities
    assert caps.streaming is True
    assert caps.files is True
    assert caps.terminal is False
    assert caps.markdown is False
    assert caps.menus is False
    assert caps.persistence is False


def test_create_transport_stdio() -> None:
    transport = create_transport("stdio")
    assert isinstance(transport, StdioTransport)


def test_get_transport_names_includes_stdio() -> None:
    assert "stdio" in get_transport_names()


@pytest.mark.asyncio
async def test_send_writes_json_line() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.send("hello world")

    written = mock_writer.write.call_args[0][0]
    obj = json.loads(written)
    assert obj["type"] == "message"
    assert obj["content"] == "hello world"
    mock_writer.drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_no_writer_is_noop() -> None:
    transport = StdioTransport()
    await transport.send("hello")


@pytest.mark.asyncio
async def test_receive_parses_json() -> None:
    transport = StdioTransport()
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    line = json.dumps({"type": "message", "content": "user says hi"}).encode() + b"\n"
    mock_reader.readline.return_value = line
    transport._reader = mock_reader

    result = await transport.receive()
    assert result == "user says hi"


@pytest.mark.asyncio
async def test_receive_returns_empty_on_eof() -> None:
    transport = StdioTransport()
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.readline.return_value = b""
    transport._reader = mock_reader

    result = await transport.receive()
    assert result == ""


@pytest.mark.asyncio
async def test_receive_no_reader_returns_empty() -> None:
    transport = StdioTransport()
    result = await transport.receive()
    assert result == ""


@pytest.mark.asyncio
async def test_receive_fallback_plain_text() -> None:
    transport = StdioTransport()
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.readline.return_value = b"plain text input\n"
    transport._reader = mock_reader

    result = await transport.receive()
    assert result == "plain text input"


@pytest.mark.asyncio
async def test_receive_json_without_content_key() -> None:
    transport = StdioTransport()
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.readline.return_value = b'{"type": "ping"}\n'
    transport._reader = mock_reader

    result = await transport.receive()
    assert result == ""


@pytest.mark.asyncio
async def test_route_with_context() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.route("builder", context="build auth")

    written = mock_writer.write.call_args[0][0]
    obj = json.loads(written)
    assert "builder" in obj["content"]
    assert "build auth" in obj["content"]


@pytest.mark.asyncio
async def test_route_without_context() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.route("planner", context=None)

    written = mock_writer.write.call_args[0][0]
    obj = json.loads(written)
    assert "planner" in obj["content"]


@pytest.mark.asyncio
async def test_stop_closes_writer() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.stop()

    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()
    assert transport._writer is None


@pytest.mark.asyncio
async def test_stop_no_writer_is_noop() -> None:
    transport = StdioTransport()
    await transport.stop()


@pytest.mark.asyncio
async def test_send_multiline_message() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.send("line one\nline two")

    written = mock_writer.write.call_args[0][0]
    obj = json.loads(written)
    assert obj["content"] == "line one\nline two"


@pytest.mark.asyncio
async def test_send_unicode_message() -> None:
    transport = StdioTransport()
    mock_writer = AsyncMock()
    transport._writer = mock_writer

    await transport.send("héllo wörld 🌍")

    written = mock_writer.write.call_args[0][0]
    obj = json.loads(written)
    assert obj["content"] == "héllo wörld 🌍"
