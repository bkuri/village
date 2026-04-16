from __future__ import annotations

import io
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import click

from village.chat.transports import AsyncTransport
from village.prompt import PromptBridge, set_bridge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandEntry:
    name: str
    description: str
    handler: Callable[..., Awaitable[str]]
    interactive: bool = True


class ProgressStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._progress: list[str] = []
        self._last_poll_idx: int = 0

    def write(self, s: str) -> int:
        with self._lock:
            n = super().write(s)
            if s:
                self._progress.append(s)
            return n

    def drain_progress(self) -> str:
        with self._lock:
            if self._last_poll_idx >= len(self._progress):
                return ""
            chunks = self._progress[self._last_poll_idx :]
            self._last_poll_idx = len(self._progress)
            return "".join(chunks)

    @property
    def has_progress(self) -> bool:
        with self._lock:
            return self._last_poll_idx < len(self._progress)


@dataclass
class PendingCommand:
    future: Future[str]
    bridge: PromptBridge
    cmd_name: str
    output: str = ""
    progress: ProgressStream | None = None


async def _invoke_click_command(
    cmd_name: str,
    cmd: click.Command,
    args: list[str],
    ctx: dict[str, Any],
) -> str:
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            cmd.main(args=args, standalone_mode=False, prog_name=cmd_name)
    except click.ClickException as e:
        return f"Error: {e.format_message()}"
    except SystemExit:
        pass

    output = stdout_buf.getvalue()
    err = stderr_buf.getvalue()
    if err and not output:
        return err.strip()
    if output and err:
        return (output + "\n" + err).strip()
    return output.strip()


_executor: ThreadPoolExecutor | None = None


def start_command_executor(max_workers: int = 4) -> None:
    global _executor
    _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="village-cmd")


def stop_command_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None


def _run_command_in_thread(
    cmd_name: str,
    cmd: click.Command,
    args: list[str],
    bridge: PromptBridge,
    cwd: str | None = None,
    progress: ProgressStream | None = None,
) -> str:
    import os

    stdout_buf: io.StringIO = progress or io.StringIO()
    stderr_buf = io.StringIO()
    prev_cwd: str | None = None
    if cwd:
        prev_cwd = os.getcwd()
        os.chdir(cwd)
    set_bridge(bridge)
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            cmd.main(args=args, standalone_mode=False, prog_name=cmd_name)
    except click.ClickException as e:
        return f"Error: {e.format_message()}"
    except SystemExit:
        pass
    finally:
        set_bridge(None)
        if prev_cwd:
            os.chdir(prev_cwd)

    output = stdout_buf.getvalue()
    err = stderr_buf.getvalue()
    if err and not output:
        return err.strip()
    if output and err:
        return (output + "\n" + err).strip()
    return output.strip()


def spawn_command(cmd_name: str, cmd: click.Command, args: list[str], cwd: str | None = None) -> PendingCommand:
    if _executor is None:
        start_command_executor()
    assert _executor is not None
    bridge = PromptBridge()
    progress = ProgressStream()
    future = _executor.submit(_run_command_in_thread, cmd_name, cmd, args, bridge, cwd, progress)
    return PendingCommand(future=future, bridge=bridge, cmd_name=cmd_name, progress=progress)


def spawn_command_by_name(cmd_name: str, args: list[str], cwd: str | None = None) -> PendingCommand | None:
    try:
        click_cmds = _get_cli_commands()
    except Exception:
        click_cmds = {}

    cmd = click_cmds.get(cmd_name)
    if cmd is None:
        return None
    return spawn_command(cmd_name, cmd, args, cwd=cwd)


def _get_cli_commands() -> dict[str, click.Command]:
    from village.cli import (
        builder,
        council,
        doctor,
        goals,
        greeter,
        lifecycle,
        planner,
        scribe,
        tasks,
        watcher,
    )

    cmds: dict[str, click.Command] = {}
    for name in ["new", "up", "down"]:
        cmds[name] = lifecycle.lifecycle_group.commands[name]
    cmds["goals"] = goals.goals
    cmds["greeter"] = greeter.greeter
    cmds["tasks"] = tasks.tasks
    cmds["watcher"] = watcher.watcher_group
    cmds["builder"] = builder.builder_group
    cmds["scribe"] = scribe.scribe_group
    cmds["planner"] = planner.planner_group
    cmds["council"] = council.council_group
    cmds["doctor"] = doctor.doctor_group
    return cmds


async def _click_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    cmd_name = ctx["_cmd_name"]
    click_cmd = ctx["_click_cmd"]
    arg_list = args.split() if args.strip() else []
    return await _invoke_click_command(cmd_name, click_cmd, arg_list, ctx)


async def _greeter_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    return ""


async def _tasks_list_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    from village.tasks import get_task_store

    config = ctx["config"]
    store = get_task_store(config=config)
    task_list = store.list_tasks()
    if not task_list:
        return "No tasks found."
    lines: list[str] = []
    for t in task_list:
        status_icon = {
            "open": "○",
            "in_progress": "◐",
            "done": "✓",
            "closed": "✓",
            "draft": "◇",
            "deferred": "❄",
        }.get(t.status, "?")
        lines.append(f"{status_icon} {t.id} [{t.priority}] {t.title}")
    return "\n".join(lines)


async def _tasks_ready_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    from village.tasks import get_task_store

    config = ctx["config"]
    store = get_task_store(config=config)
    task_list = store.get_ready_tasks()
    if not task_list:
        return "No tasks ready."
    lines = ["Ready tasks:"]
    for t in task_list:
        lines.append(f"  - {t.id}: {t.title} (P{t.priority})")
    return "\n".join(lines)


async def _tasks_create_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    if not args.strip():
        return "Usage: /tasks create <title>"
    from village.tasks import TaskCreate, get_task_store

    config = ctx["config"]
    store = get_task_store(config=config)
    task = store.create_task(TaskCreate(title=args.strip(), issue_type="task"))
    return f"Created task: {task.id} — {task.title}"


async def _help_handler(transport: AsyncTransport, args: str, ctx: dict[str, Any]) -> str:
    registry = _ensure_registry()
    lines = ["Available commands:", ""]
    for name, entry in registry.items():
        interactive = " (interactive)" if entry.interactive else ""
        lines.append(f"  /{name} — {entry.description}{interactive}")
    lines.append("")
    lines.append("Or just type naturally and I'll figure it out.")
    return "\n".join(lines)


def _build_registry() -> dict[str, CommandEntry]:
    registry: dict[str, CommandEntry] = {
        "help": CommandEntry(
            name="help",
            description="Show available commands",
            handler=_help_handler,
            interactive=False,
        ),
        "greeter": CommandEntry(
            name="greeter",
            description="Interactive Q&A session",
            handler=_greeter_handler,
            interactive=True,
        ),
        "tasks": CommandEntry(
            name="tasks",
            description="List all tasks",
            handler=_tasks_list_handler,
            interactive=False,
        ),
        "tasks list": CommandEntry(
            name="tasks list",
            description="List all tasks",
            handler=_tasks_list_handler,
            interactive=False,
        ),
        "tasks ready": CommandEntry(
            name="tasks ready",
            description="Show tasks ready to work on",
            handler=_tasks_ready_handler,
            interactive=False,
        ),
        "tasks create": CommandEntry(
            name="tasks create",
            description="Create a new task",
            handler=_tasks_create_handler,
            interactive=False,
        ),
    }

    try:
        click_cmds = _get_cli_commands()
    except Exception:
        return registry

    interactive_cmds = {"new", "up", "planner", "watcher", "builder", "council", "doctor"}
    for name, cmd in click_cmds.items():
        if name not in registry:

            async def _make_handler(
                transport: AsyncTransport,
                args: str,
                ctx: dict[str, Any],
                _name: str = name,
                _cmd: click.Command = cmd,
            ) -> str:
                arg_list = args.split() if args.strip() else []
                return await _invoke_click_command(_name, _cmd, arg_list, ctx)

            desc = cmd.help.split("\n")[0] if cmd.help else name
            registry[name] = CommandEntry(
                name=name,
                description=desc.strip(),
                handler=_make_handler,
                interactive=name in interactive_cmds,
            )

    return registry


COMMAND_REGISTRY: dict[str, CommandEntry] = {}
_REGISTRY_INITIALIZED = False


def _ensure_registry() -> dict[str, CommandEntry]:
    global COMMAND_REGISTRY, _REGISTRY_INITIALIZED
    if _REGISTRY_INITIALIZED:
        return COMMAND_REGISTRY
    _REGISTRY_INITIALIZED = True
    COMMAND_REGISTRY = _build_registry()
    return COMMAND_REGISTRY


GREETER_COMMANDS = {"greeter"}


def parse_command(message: str) -> tuple[str | None, list[str]]:
    stripped = message.strip()
    if not stripped:
        return None, []
    parts = stripped.split()
    cmd = parts[0]
    if cmd.startswith("/"):
        cmd = cmd[1:]
    args = parts[1:] if len(parts) > 1 else []
    return cmd, args


async def dispatch(
    transport: AsyncTransport,
    message: str,
    ctx: dict[str, Any],
) -> str | None:
    registry = _ensure_registry()
    stripped = message.strip()
    if not stripped:
        return None

    parts = stripped.split(None, 1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd.startswith("/"):
        cmd = cmd[1:]

    entry = registry.get(cmd)
    if entry:
        return await entry.handler(transport, args, ctx)

    if len(parts) >= 2:
        two_word = f"{cmd} {parts[1]}"
        entry = registry.get(two_word)
        if entry:
            remaining = parts[2:] if len(parts) > 2 else []
            return await entry.handler(transport, " ".join(remaining), ctx)

    return None
