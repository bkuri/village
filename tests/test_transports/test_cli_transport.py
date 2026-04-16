from __future__ import annotations

from unittest.mock import patch

import pytest

from village.chat.transports.cli import CLITransport


@pytest.mark.asyncio
async def test_start_prints_welcome_banner() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.echo") as mock_echo:
        await transport.start()
        mock_echo.assert_called_once_with("Village Greeter — How can I help? /exit to quit.\n")


@pytest.mark.asyncio
async def test_stop_prints_exit_message() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.echo") as mock_echo:
        await transport.stop()
        mock_echo.assert_called_once_with("\nExiting...")


@pytest.mark.asyncio
async def test_send_outputs_message() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.echo") as mock_echo:
        await transport.send("Hello, world!")
        mock_echo.assert_called_once_with("\nHello, world!\n")


@pytest.mark.asyncio
async def test_send_empty_message() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.echo") as mock_echo:
        await transport.send("")
        mock_echo.assert_called_once_with("\n\n")


@pytest.mark.asyncio
async def test_send_multiline_message() -> None:
    transport = CLITransport()
    with patch("village.chat.transports.cli.click.echo") as mock_echo:
        await transport.send("line one\nline two")
        mock_echo.assert_called_once_with("\nline one\nline two\n")


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
async def test_route_calls_run_role_chat_with_context() -> None:
    transport = CLITransport()
    with (
        patch("village.chat.transports.cli.click.echo") as mock_echo,
        patch("village.roles.run_role_chat") as mock_run,
    ):
        await transport.route("builder", context="build the auth module")
        mock_echo.assert_called_once_with("\n  ── Routing to builder ──────────")
        mock_run.assert_called_once_with("builder", context={"context": "build the auth module"})


@pytest.mark.asyncio
async def test_route_calls_run_role_chat_without_context() -> None:
    transport = CLITransport()
    with (
        patch("village.chat.transports.cli.click.echo") as mock_echo,
        patch("village.roles.run_role_chat") as mock_run,
    ):
        await transport.route("planner", context=None)
        mock_echo.assert_called_once_with("\n  ── Routing to planner ──────────")
        mock_run.assert_called_once_with("planner", context=None)


@pytest.mark.asyncio
async def test_route_with_empty_context() -> None:
    transport = CLITransport()
    with (
        patch("village.chat.transports.cli.click.echo") as mock_echo,
        patch("village.roles.run_role_chat") as mock_run,
    ):
        await transport.route("scribe", context="")
        mock_echo.assert_called_once_with("\n  ── Routing to scribe ──────────")
        mock_run.assert_called_once_with("scribe", context=None)
