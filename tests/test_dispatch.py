from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest

from village.chat.transports import AsyncTransport, TransportCapabilities
from village.dispatch import (
    COMMAND_REGISTRY,
    PendingCommand,
    _ensure_registry,
    dispatch,
    parse_command,
    spawn_command,
    spawn_command_by_name,
    start_command_executor,
    stop_command_executor,
)
from village.prompt import set_bridge

_ensure_registry()


def _make_transport() -> AsyncTransport:
    transport = MagicMock(spec=AsyncTransport)
    transport.send = AsyncMock()
    transport.receive = AsyncMock(return_value="")
    transport.name = "mock"
    transport.capabilities = TransportCapabilities()
    return transport


def _make_ctx() -> dict[str, Any]:
    @dataclass
    class MockConfig:
        pass

    return {"config": MockConfig()}


def _make_task(title: str, task_id: str, status: str, priority: int = 2) -> Any:
    task = MagicMock()
    task.id = task_id
    task.title = title
    task.status = status
    task.priority = priority
    return task


@pytest.mark.asyncio
async def test_dispatch_help() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "/help", ctx)
    assert result is not None
    assert "Available commands:" in result
    for name in COMMAND_REGISTRY:
        assert f"/{name}" in result or f"/{name.split()[0]}" in result
    assert "Or just type naturally" in result


@pytest.mark.asyncio
async def test_dispatch_tasks() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    mock_tasks = [_make_task("Fix auth bug", "bd-a1b2", "open", 1)]

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = mock_tasks
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks", ctx)
        assert result is not None
        assert "bd-a1b2" in result
        assert "Fix auth bug" in result
        assert "○" in result


@pytest.mark.asyncio
async def test_dispatch_tasks_no_tasks() -> None:
    transport = _make_transport()
    ctx = _make_ctx()

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = []
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks", ctx)
        assert result == "No tasks found."


@pytest.mark.asyncio
async def test_dispatch_tasks_ready() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    mock_tasks = [_make_task("Add login page", "bd-c3d4", "open", 0)]

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = mock_tasks
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks ready", ctx)
        assert result is not None
        assert "bd-c3d4" in result
        assert "Add login page" in result


@pytest.mark.asyncio
async def test_dispatch_tasks_ready_no_tasks() -> None:
    transport = _make_transport()
    ctx = _make_ctx()

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = []
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks ready", ctx)
        assert result == "No tasks found."


@pytest.mark.asyncio
async def test_dispatch_tasks_create() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    mock_tasks = [_make_task("Existing", "bd-1111", "open")]

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = mock_tasks
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks create Build the API", ctx)
        assert result is not None
        mock_store.list_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_tasks_create_no_title() -> None:
    transport = _make_transport()
    ctx = _make_ctx()

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = []
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "/tasks create", ctx)
        assert result == "No tasks found."


@pytest.mark.asyncio
async def test_dispatch_unknown_returns_none() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "/nonexistent", ctx)
    assert result is None


@pytest.mark.asyncio
async def test_dispatch_without_slash() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "help", ctx)
    assert result is not None
    assert "Available commands:" in result


@pytest.mark.asyncio
async def test_dispatch_two_word_commands() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    mock_tasks = [_make_task("Task one", "bd-1111", "open")]

    with patch("village.tasks.get_task_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = mock_tasks
        mock_get_store.return_value = mock_store

        result = await dispatch(transport, "tasks list", ctx)
        assert result is not None
        assert "bd-1111" in result


@pytest.mark.asyncio
async def test_dispatch_empty_returns_none() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "", ctx)
    assert result is None


@pytest.mark.asyncio
async def test_dispatch_whitespace_only_returns_none() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "   ", ctx)
    assert result is None


@pytest.mark.asyncio
async def test_dispatch_two_word_fallback_when_single_not_found() -> None:
    transport = _make_transport()
    ctx = _make_ctx()

    with patch(
        "village.dispatch.COMMAND_REGISTRY",
        {
            "tasks ready": _ensure_registry().get("tasks ready"),
        },
    ):
        mock_tasks = [_make_task("Ready task", "bd-rr01", "open", 0)]

        with patch("village.tasks.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_ready_tasks.return_value = mock_tasks
            mock_get_store.return_value = mock_store

            result = await dispatch(transport, "/tasks ready", ctx)
            assert result is not None
            assert "Ready tasks:" in result
            assert "bd-rr01" in result


@pytest.mark.asyncio
async def test_dispatch_greeter_returns_empty() -> None:
    transport = _make_transport()
    ctx = _make_ctx()
    result = await dispatch(transport, "/greeter", ctx)
    assert result == ""


def test_parse_command_with_slash() -> None:
    cmd, args = parse_command("/help")
    assert cmd == "help"
    assert args == []


def test_parse_command_with_args() -> None:
    cmd, args = parse_command("/tasks create Build the API")
    assert cmd == "tasks"
    assert args == ["create", "Build", "the", "API"]


def test_parse_command_without_slash() -> None:
    cmd, args = parse_command("help")
    assert cmd == "help"
    assert args == []


def test_parse_command_empty() -> None:
    cmd, args = parse_command("")
    assert cmd is None
    assert args == []


def test_parse_command_whitespace_only() -> None:
    cmd, args = parse_command("   ")
    assert cmd is None
    assert args == []


def test_spawn_command_returns_pending() -> None:
    stop_command_executor()

    @click.command()
    def _echo() -> None:
        click.echo("hello from spawn")

    pending = spawn_command("echo", _echo, [])
    assert isinstance(pending, PendingCommand)
    assert pending.cmd_name == "echo"
    assert pending.bridge is not None
    result = pending.future.result(timeout=5.0)
    assert "hello from spawn" in result
    stop_command_executor()


def test_spawn_command_by_name_unknown_returns_none() -> None:
    stop_command_executor()
    result = spawn_command_by_name("nonexistent_xyz_cmd", [])
    assert result is None


def test_start_and_stop_command_executor() -> None:
    stop_command_executor()
    start_command_executor(max_workers=2)
    from village.dispatch import _executor

    assert _executor is not None
    stop_command_executor()
    from village.dispatch import _executor as exec2

    assert exec2 is None


def test_spawn_command_sets_and_clears_bridge() -> None:
    from village.prompt import get_bridge

    stop_command_executor()
    set_bridge(None)

    bridge_during: list[object] = []

    @click.command()
    def _check_bridge() -> None:
        bridge_during.append(get_bridge())

    pending = spawn_command("check_bridge", _check_bridge, [])
    pending.future.result(timeout=5.0)
    assert len(bridge_during) == 1
    assert bridge_during[0] is pending.bridge
    assert get_bridge() is None
    stop_command_executor()
