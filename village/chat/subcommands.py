"""Subcommand registry and execution (read-only)."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from village.chat.drafts import delete_draft, list_drafts, load_draft
from village.probes.tools import SubprocessError, run_command_output
from village.status import collect_full_status

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object


@dataclass
class SubcommandResult:
    """Result of subcommand execution."""

    stdout: str
    stderr: str
    exit_code: int


@dataclass
class ParsedCommand:
    """Parsed user input as subcommand."""

    command: str | None
    args: list[str]
    error: str | None


SUBCOMMANDS = {
    "/tasks": {"handler": "bd_list", "description": "List all Beads tasks", "args": []},
    "/task": {"handler": "bd_show", "description": "Show task details", "args": ["id"]},
    "/ready": {"handler": "bd_ready", "description": "Show ready tasks (Beads)", "args": []},
    "/status": {
        "handler": "village_status",
        "description": "Show Village status summary",
        "args": [],
    },
    "/help": {"handler": "help_text", "description": "Show chat help", "args": ["topic"]},
    "/queue": {"handler": "bd_ready", "description": "Alias for /ready", "args": []},
    "/lock": {"handler": "village_locks", "description": "Show active locks", "args": []},
    "/cleanup": {
        "handler": "village_cleanup_plan",
        "description": "Show cleanup plan (read-only)",
        "args": [],
    },
    "/create": {
        "handler": "task_create",
        "description": "Enter task-create mode",
        "args": ["title"],
    },
    "/enable": {
        "handler": "task_enable",
        "description": "Enable draft(s) for batch submission",
        "args": ["id|all"],
    },
    "/edit": {"handler": "task_edit", "description": "Edit existing draft", "args": ["id"]},
    "/discard": {"handler": "task_discard", "description": "Delete draft", "args": ["id"]},
    "/submit": {
        "handler": "task_submit",
        "description": "Review and confirm batch of enabled drafts",
        "args": [],
    },
    "/confirm": {
        "handler": "task_confirm",
        "description": "Confirm and create Beads tasks from enabled drafts",
        "args": [],
    },
    "/confirm": {
        "handler": "task_confirm",
        "description": "Confirm and create Beads tasks from enabled drafts",
        "args": [],
    },
    "/reset": {
        "handler": "task_reset",
        "description": "Rollback session: delete created tasks, restore context",
        "args": [],
    },
    "/drafts": {
        "handler": "task_list_drafts",
        "description": "List all draft tasks",
        "args": [],
    },
    "/brainstorm": {
        "handler": "task_brainstorm",
        "description": "Break down task using Sequential Thinking",
        "args": ["title"],
    },
}


def parse_command(user_input: str) -> ParsedCommand:
    """
    Parse user input as subcommand.

    Args:
        user_input: User's input string

    Returns:
        ParsedCommand with command name, args, or error
    """
    user_input = user_input.strip()

    if not user_input.startswith("/"):
        return ParsedCommand(command=None, args=[], error=None)

    parts = user_input.split(maxsplit=1)
    command = parts[0]

    if command not in SUBCOMMANDS:
        return ParsedCommand(command=None, args=[], error=f"Unknown subcommand: {command}")

    args = parts[1].split() if len(parts) > 1 else []

    return ParsedCommand(command=command[1:], args=args, error=None)


def execute_command(command: str, args: list[str], config: _Config) -> SubcommandResult:
    """
    Execute read-only subcommand.

    Args:
        command: Command name (without slash)
        args: Command arguments
        config: Village config

    Returns:
        SubcommandResult with stdout, stderr, exit_code
    """
    handlers = {
        "bd_list": _bd_list,
        "bd_show": _bd_show,
        "bd_ready": _bd_ready,
        "village_status": _village_status,
        "help_text": _help_text,
        "village_locks": _village_locks,
        "village_cleanup_plan": _village_cleanup_plan,
        "task_create": _task_create,
        "task_enable": _task_enable,
        "task_edit": _task_edit,
        "task_discard": _task_discard,
        "task_submit": _task_submit,
        "task_reset": _task_reset,
        "task_list_drafts": _task_list_drafts,
        "task_brainstorm": _task_brainstorm,
    }

    handler = handlers.get(command)
    if not handler:
        return SubcommandResult(stdout="", stderr=f"Unknown command: {command}", exit_code=1)

    try:
        stdout, stderr, exit_code = handler(args, config)
        return SubcommandResult(stdout=stdout, stderr=stderr, exit_code=exit_code)
    except Exception as e:
        logger.error(f"Command {command} failed: {e}")
        return SubcommandResult(stdout="", stderr=str(e), exit_code=1)


def _bd_list(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `bd list`."""
    try:
        output = run_command_output(["bd", "list"])
        return output, "", 0
    except SubprocessError as e:
        return "", str(e), 1


def _bd_show(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `bd show <id>`."""
    if not args:
        return "", "Error: /task requires <id> argument", 1

    try:
        output = run_command_output(["bd", "show", args[0]])
        return output, "", 0
    except SubprocessError as e:
        return "", str(e), 1


def _bd_ready(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `bd ready`."""
    try:
        output = run_command_output(["bd", "ready"])
        return output, "", 0
    except SubprocessError as e:
        return "", str(e), 1


def _village_status(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `village status --short`."""
    from village.render.text import render_full_status

    full_status = collect_full_status(config.tmux_session)
    flags_dict = {"workers": False, "locks": False, "orphans": False}
    output = render_full_status(full_status, flags_dict)
    return output, "", 0


def _help_text(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Show help text."""
    help_text = """# Village Chat — Slash Commands

## Commands
- `/help [topic]` — show help (topics: commands, tasks, context, files, policy, workflow)
- `/tasks` — list Beads tasks
- `/task <id>` — show task details
- `/ready` — show ready tasks (Beads)
- `/status` — show Village status summary
- `/queue` — alias for /ready
- `/lock` — show active locks
- `/cleanup` — show cleanup plan (read-only)
- `/create [title]` — enter task-create mode to define new task
- `/enable <id|all>` — enable draft(s) for batch submission
- `/edit <id>` — edit existing draft
- `/discard <id>` — delete draft
- `/submit` — review and submit batch of enabled drafts
- `/reset` — rollback session: delete created tasks, restore context
- `/drafts` — list all draft tasks

## Workflow
1. Use chat to clarify intent and write context files.
2. Use Beads to define work.
3. Use `village ready` to validate execution readiness.
4. Use `village queue` / `village resume` to execute.

## Task Creation Workflow
1. `/create [title]` — start task creation mode
2. Answer Q&A phases (goal, context, success, validation)
3. Draft saved to `.village/drafts/`
4. `/enable <draft-id>` — mark for submission
5. `/submit` — review and confirm batch creation
6. `/reset` — rollback if needed

## Files
By default, chat writes to:
`.village/context/`

Draft tasks stored in:
`.village/drafts/`
"""

    if args:
        topic = args[0].lower()
        if topic == "commands":
            help_text = """## Commands

- `/help [topic]` — show help
- `/tasks` — list Beads tasks
- `/task <id>` — show task details
- `/ready` — show ready tasks (Beads)
- `/status` — show Village status summary
- `/queue` — alias for /ready
- `/lock` — show active locks
- `/cleanup` — show cleanup plan (read-only)
- `/create [title]` — enter task-create mode
- `/enable <id|all>` — enable draft(s) for submission
- `/edit <id>` — edit existing draft
- `/discard <id>` — delete draft
- `/submit` — review and submit batch
- `/reset` — rollback session
- `/drafts` — list all draft tasks
"""
        elif topic == "tasks":
            help_text = """## Tasks

Use `/tasks` to list all Beads tasks.
Use `/task <id>` to show details for a specific task.

## Task Creation
Use `/create [title]` to enter task creation mode.
Drafts are saved to `.village/drafts/` and can be submitted in batches.
"""
        elif topic == "context":
            help_text = """## Context Files

Chat writes context files to `.village/context/`:
- project.md
- goals.md
- constraints.md
- assumptions.md
- decisions.md
- open-questions.md
"""
        elif topic == "files":
            help_text = """## Files

Context files are written incrementally as you chat.
All files are stored in `.village/context/`.

Draft tasks are stored in `.village/drafts/`.
"""
        elif topic == "policy":
            help_text = """## Policy

Village Chat is a knowledge-sharing facilitator.
It does not execute work or schedule agents.
See `/help workflow` for proper usage.
"""
        elif topic == "workflow":
            help_text = """## Workflow

1. Use chat to clarify intent and write context files.
2. Use Beads to define work.
3. Use `village ready` to validate execution readiness.
4. Use `village queue` / `village resume` to execute.

## Task Creation Workflow
1. `/create [title]` — start task creation
2. Answer Q&A phases
3. `/enable <draft-id>` — mark for submission
4. `/submit` — confirm batch creation
5. `/reset` — rollback if needed
"""
        elif topic == "drafts":
            help_text = """## Drafts

Draft tasks are saved to `.village/drafts/`.
Use `/drafts` to list all drafts.
Use `/enable <draft-id>` to mark for submission.
Use `/submit` to create tasks from enabled drafts.
Use `/reset` to rollback session (deletes created tasks, restores context).
"""
        else:
            help_text = (
                f"Unknown topic: {args[0]}\nAvailable: "
                f"commands, tasks, context, files, policy, workflow, drafts"
            )

    return help_text, "", 0


def _village_locks(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `village locks`."""
    from village.render.text import render_worker_table
    from village.status import collect_workers

    workers = collect_workers(config.tmux_session)
    output = render_worker_table(workers)
    return output, "", 0


def _village_cleanup_plan(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Execute `village cleanup --plan`."""
    from village.cleanup import plan_cleanup

    cleanup_plan = plan_cleanup(config.tmux_session)

    if not cleanup_plan.stale_locks:
        return "No stale locks found", "", 0

    output = f"Found {len(cleanup_plan.stale_locks)} stale locks:\n"
    for lock in cleanup_plan.stale_locks:
        output += f"  - {lock.task_id} (pane: {lock.pane_id})\n"

    output += "\n(preview: nothing removed)"
    return output, "", 0


def get_available_commands() -> list[str]:
    """
    Get list of available subcommands.

    Returns:
        List of command names (without leading slash)
    """
    return [cmd[1:] for cmd in SUBCOMMANDS.keys()]


def _task_create(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Enter task-create mode with optional title."""
    title = " ".join(args) if args else "Untitled Task"
    return f"Creating task: {title}", "", 0


def _task_enable(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Enable draft(s) for batch submission."""
    if not args:
        return "", "Error: /enable requires <draft-id> or 'all'", 1

    if args[0] == "all":
        return "Enabled all drafts", "", 0

    draft_id = args[0]
    try:
        load_draft(draft_id, config)
        return f"Enabled draft: {draft_id}", "", 0
    except FileNotFoundError:
        return "", f"Draft not found: {draft_id}", 1


def _task_edit(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Edit existing draft."""
    if not args:
        return "", "Error: /edit requires <draft-id>", 1

    draft_id = args[0]
    try:
        draft = load_draft(draft_id, config)
        return f"Editing draft: {draft_id}\n\nTitle: {draft.title}", "", 0
    except FileNotFoundError:
        return "", f"Draft not found: {draft_id}", 1


def _task_discard(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Delete draft."""
    if not args:
        return "", "Error: /discard requires <draft-id>", 1

    draft_id = args[0]
    try:
        delete_draft(draft_id, config)
        return f"Discarded draft: {draft_id}", "", 0
    except FileNotFoundError:
        return "", f"Draft not found: {draft_id}", 1


def _task_submit(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Submit batch of enabled drafts."""
    from village.chat.state import load_session_state

    state = load_session_state(config)
    pending = state.get("pending_enables", [])

    if not pending:
        return "", "Error: No drafts enabled. Use `/enable <draft-id>` first.", 1

    return f"Submitting {len(pending)} draft(s)", "", 0


def _task_confirm(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Confirm batch submission to create Beads tasks."""
    from village.chat.state import load_session_state, save_session_state
    from village.chat.task_extractor import create_draft_tasks, extract_beads_specs

    state_dict = load_session_state(config)
    pending = state_dict.get("pending_enables", [])

    if not pending:
        return "", "Error: No drafts enabled. Use `/enable <draft-id>` first.", 1

    try:
        baseline = state_dict.get("session_snapshot", {}).get("brainstorm_baseline", {})
        breakdown = state_dict.get("session_snapshot", {}).get("task_breakdown", {})
        config_git_root_name = config.git_root.name

        specs = extract_beads_specs(
            baseline,
            breakdown,
            config_git_root_name,
        )

        created_tasks = create_draft_tasks(specs, config)
        created_ids = list(created_tasks.values())

        # Update session state with created task IDs
        snapshot = state_dict.get("session_snapshot", {})
        snapshot["brainstorm_created_ids"] = created_ids
        state_dict["created_task_ids"] = created_ids
        save_session_state(config, state_dict)

        return f"Created {len(created_tasks)} task(s) in Beads", "", 0
    except Exception as e:
        return "", f"Error creating tasks: {e}", 1


def _task_reset(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Rollback session."""
    from village.chat.state import load_session_state

    state = load_session_state(config)
    created = state.get("created_task_ids", [])

    if not created:
        return "", "Error: No tasks created in this session. Nothing to reset.", 1

    return f"Rolling back {len(created)} task(s)", "", 0


def _task_list_drafts(args: list[str], config: _Config) -> tuple[str, str, int]:
    """List all draft tasks."""
    drafts = list_drafts(config)

    if not drafts:
        return "No drafts found", "", 0

    lines = ["Draft tasks:\n"]
    for draft in drafts:
        lines.append(f"  • {draft.id} [{draft.scope}] {draft.title}")
        lines.append(f"      Created: {draft.created_at.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines), "", 0


def _task_brainstorm(args: list[str], config: _Config) -> tuple[str, str, int]:
    """Handle /brainstorm command (runs in conversation, not read-only)."""
    return "", "Use /brainstorm in conversation mode", 0
