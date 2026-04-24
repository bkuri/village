from __future__ import annotations

from unittest.mock import patch

import pytest

from village.chat.transports.cli import CLITransport


@pytest.mark.asyncio
async def test_start_prints_welcome_banner(capsys) -> None:
    transport = CLITransport()
    await transport.start()
    captured = capsys.readouterr()
    assert "Village Greeter" in captured.out
    assert "/exit to quit" in captured.out


@pytest.mark.asyncio
async def test_stop_prints_exit_message(capsys) -> None:
    transport = CLITransport()
    await transport.stop()
    captured = capsys.readouterr()
    assert "Exiting..." in captured.out


@pytest.mark.asyncio
async def test_send_outputs_message(capsys) -> None:
    transport = CLITransport()
    await transport.send("Hello, world!")
    captured = capsys.readouterr()
    assert "Hello, world!" in captured.out


@pytest.mark.asyncio
async def test_send_empty_message(capsys) -> None:
    transport = CLITransport()
    await transport.send("")
    captured = capsys.readouterr()
    assert captured.out == "\n\n\n"


@pytest.mark.asyncio
async def test_send_multiline_message(capsys) -> None:
    transport = CLITransport()
    await transport.send("line one\nline two")
    captured = capsys.readouterr()
    assert "line one" in captured.out
    assert "line two" in captured.out


@pytest.mark.asyncio
async def test_receive_reads_from_stdin() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.prompt", return_value="user input"):
        result = await transport.receive()
        assert result == "user input"


@pytest.mark.asyncio
async def test_receive_empty_input() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.prompt", return_value=""):
        result = await transport.receive()
        assert result == ""


def test_name_returns_cli() -> None:
    transport = CLITransport()
    assert transport.name == "cli"


@pytest.mark.asyncio
async def test_route_calls_run_role_chat_with_context(capsys) -> None:
    transport = CLITransport()
    with patch("village.roles.run_role_chat") as mock_run:
        await transport.route("builder", context="build the auth module")
    captured = capsys.readouterr()
    assert "Routing to builder" in captured.out
    mock_run.assert_called_once_with("builder", context={"context": "build the auth module"})


@pytest.mark.asyncio
async def test_route_calls_run_role_chat_without_context(capsys) -> None:
    transport = CLITransport()
    with patch("village.roles.run_role_chat") as mock_run:
        await transport.route("planner", context=None)
    captured = capsys.readouterr()
    assert "Routing to planner" in captured.out
    mock_run.assert_called_once_with("planner", context=None)


@pytest.mark.asyncio
async def test_route_with_empty_context(capsys) -> None:
    transport = CLITransport()
    with patch("village.roles.run_role_chat") as mock_run:
        await transport.route("scribe", context="")
    captured = capsys.readouterr()
    assert "Routing to scribe" in captured.out
    mock_run.assert_called_once_with("scribe", context=None)
