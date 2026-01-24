"""Core conversation orchestration."""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from village.chat.context import (
    ContextFile,
    ContextUpdate,
    apply_context_update,
    get_context_dir,
    get_current_context,
)
from village.chat.drafts import (
    DraftTask,
    delete_draft,
    generate_draft_id,
    list_drafts,
    load_draft,
    save_draft,
)
from village.chat.prompts import ChatMode, generate_initial_prompt, generate_mode_prompt
from village.chat.schema import validate_schema
from village.chat.state import (
    SessionSnapshot,
    save_session_state,
    take_session_snapshot,
)
from village.chat.subcommands import execute_command, parse_command
from village.probes.tools import SubprocessError, run_command_output

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    _Config = object
    Config = object  # type: ignore[misc]

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """Single message in conversation."""

    role: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Conversation state across turns."""

    messages: list[ConversationMessage] = field(default_factory=list)
    context_files: dict[str, ContextFile] = field(default_factory=dict)
    subcommand_results: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    mode: str = "knowledge-share"
    pending_enables: list[str] = field(default_factory=list)
    session_snapshot: SessionSnapshot | None = None
    batch_submitted: bool = False
    context_diffs: dict[str, str] = field(default_factory=dict)
    active_draft_id: str | None = None


def start_conversation(config: _Config, mode: str = "knowledge-share") -> ConversationState:
    """
    Initialize conversation with initial prompt.

    Args:
        config: Village config
        mode: Chat mode (knowledge-share or task-create)

    Returns:
        ConversationState with initial system prompt
    """
    if mode == "task-create":
        prompt = generate_mode_prompt(config, ChatMode.TASK_CREATE)[0]
    else:
        prompt = generate_initial_prompt(config)[0]

    logger.info(f"Starting chat with mode: {mode}")

    context_dir = get_context_dir(config)
    context_files = get_current_context(context_dir)

    context_summary = ""
    if context_files:
        context_summary = "\n\n## Existing Context\n\n"
        for filename, ctx_file in context_files.items():
            context_summary += f"### {filename}\n{ctx_file.content[:200]}...\n\n"

    state = ConversationState(
        messages=[
            ConversationMessage(
                role="system",
                content=prompt + context_summary,
            )
        ],
        context_files=context_files,
        mode=mode,
    )

    if mode == "task-create":
        snapshot = take_session_snapshot(state, config)
        state.session_snapshot = snapshot

    return state


def process_user_input(
    state: ConversationState, user_input: str, config: _Config
) -> ConversationState:
    """
    Process user input (command or conversational).

    Args:
        state: Current conversation state
        user_input: User's input string
        config: Village config

    Returns:
        Updated ConversationState
    """
    state.messages.append(ConversationMessage(role="user", content=user_input))

    parsed = parse_command(user_input)

    if parsed.command in {"create", "enable", "edit", "discard", "submit", "reset", "drafts"}:
        state = _handle_task_subcommand(state, parsed.command, parsed.args, config)
        return state

    if parsed.command:
        result = execute_command(parsed.command, parsed.args, config)
        injection_lines = [
            f"### Subcommand: /{parsed.command}",
            "",
            "stdout:",
            result.stdout,
            "",
            "stderr:",
            result.stderr,
        ]
        injection = "\n".join(injection_lines)
        state.messages.append(ConversationMessage(role="user", content=injection))
        state.subcommand_results[parsed.command] = result.stdout
        return state

    llm_response = _call_llm(state.messages, config, mode=state.mode)

    update = _parse_llm_response(llm_response)

    if update.error:
        state.errors.append(f"Failed to parse LLM response: {update.error}")
        state.messages.append(ConversationMessage(role="assistant", content=llm_response))
        return state

    context_dir = get_context_dir(config)
    try:
        written_files = apply_context_update(context_dir, update)
        for filename, content in update.writes.items():
            state.context_files[filename] = ContextFile(
                name=filename, path=written_files[filename], content=content
            )
    except Exception as e:
        state.errors.append(f"Failed to write context files: {e}")
        logger.error(f"Failed to write context files: {e}")

    state.messages.append(ConversationMessage(role="assistant", content=llm_response))

    return state


def _parse_llm_response(content: str) -> ContextUpdate:
    """
    Parse JSON response from LLM.

    Args:
        content: Raw LLM response string

    Returns:
        ContextUpdate with parsed data or error
    """
    try:
        json_str = _extract_json(content)
        data = json.loads(json_str)

        errors = validate_schema(data)
        if errors:
            error_msg = "; ".join([f"{e.field}: {e.message}" for e in errors])
            return ContextUpdate(writes={}, notes=[], open_questions=[], error=error_msg)

        writes = data.get("writes", {})
        notes = data.get("notes", [])
        open_questions = data.get("open_questions", [])

        return ContextUpdate(writes=writes, notes=notes, open_questions=open_questions)
    except (json.JSONDecodeError, ValueError) as e:
        return ContextUpdate(writes={}, notes=[], open_questions=[], error=str(e))


def _extract_json(content: str) -> str:
    """
    Extract JSON from LLM response.

    Handles:
    - Raw JSON
    - Markdown code fences (```json ... ```)
    - Triple backticks without language (``` ... ```)

    Args:
        content: Raw LLM response

    Returns:
        Extracted JSON string
    """
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\n(.+?)```", content, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    return content


def _call_llm(
    messages: list[ConversationMessage], config: _Config, mode: str = "knowledge-share"
) -> str:
    """
    Call LLM via backend subprocess.

    Args:
        messages: Conversation messages
        config: Village config
        mode: Chat mode (knowledge-share or task-create)

    Returns:
        LLM response string
    """
    conversation = "\n\n".join([f"{m.role}: {m.content}" for m in messages[-10:]])

    try:
        result = subprocess.run(
            ["opencode", "run"],
            input=conversation,
            cwd=config.git_root,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error(f"OpenCode failed with code {result.returncode}: {result.stderr}")
            return f"Error: OpenCode execution failed ({result.returncode})"

        return result.stdout
    except subprocess.TimeoutExpired:
        logger.error("OpenCode call timed out")
        return "Error: OpenCode call timed out (30s)"
    except FileNotFoundError:
        logger.error("OpenCode not found")
        return "Error: OpenCode not found in PATH"
    except Exception as e:
        logger.error(f"OpenCode call failed: {e}")
        return f"Error: Failed to call OpenCode ({e})"


def _handle_task_subcommand(
    state: ConversationState, command: str, args: list[str], config: _Config
) -> ConversationState:
    """
    Handle task-related subcommands (/create, /enable, /edit, /discard, /submit, /reset, /drafts).

    Args:
        state: Current conversation state
        command: Command name
        args: Command arguments
        config: Village config

    Returns:
        Updated ConversationState
    """
    if command == "create":
        state = _switch_to_create_mode(args, state, config)
    elif command == "enable":
        state = _handle_enable(args, state, config)
    elif command == "edit":
        state = _handle_edit(args, state, config)
    elif command == "discard":
        state = _handle_discard(args, state, config)
    elif command == "submit":
        state = _handle_submit(state, config)
    elif command == "reset":
        state = _handle_reset(state, config)
    elif command == "drafts":
        state = _handle_drafts(state, config)

    save_session_state(state, config)
    return state


def _switch_to_create_mode(
    args: list[str], state: ConversationState, config: _Config
) -> ConversationState:
    """
    Switch to task-create mode with optional title.

    Args:
        args: Command arguments (title)
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    title = " ".join(args) if args else "Untitled Task"

    draft = DraftTask(
        id=generate_draft_id(),
        created_at=datetime.now(),
        title=title,
        description="",
        scope="feature",
    )

    save_draft(draft, config)
    state.pending_enables.append(draft.id)
    state.mode = "task-create"

    snapshot = take_session_snapshot(state, config)
    state.session_snapshot = snapshot

    message = (
        f"Task creation mode enabled. Draft ID: {draft.id}\n\n"
        f"Starting Q&A Phase 1: What is the goal of this task?"
    )
    state.messages.append(ConversationMessage(role="assistant", content=message))

    return state


def _handle_enable(args: list[str], state: ConversationState, config: _Config) -> ConversationState:
    """
    Enable draft(s) for batch submission.

    Args:
        args: Command arguments (draft ID or "all")
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    if not args:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content="Error: /enable requires <draft-id> or 'all'",
            )
        )
        return state

    if args[0] == "all":
        drafts = list_drafts(config)
        enabled_ids = [d.id for d in drafts if d.id not in state.pending_enables]
        state.pending_enables.extend(enabled_ids)
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=f"Enabled {len(enabled_ids)} drafts for submission",
            )
        )
    else:
        draft_id = args[0]
        try:
            load_draft(draft_id, config)
            if draft_id not in state.pending_enables:
                state.pending_enables.append(draft_id)
            state.messages.append(
                ConversationMessage(
                    role="assistant",
                    content=f"Enabled draft: {draft_id}",
                )
            )
        except FileNotFoundError:
            error_msg = f"Error: Draft not found: {draft_id}"
            state.errors.append(error_msg)
            state.messages.append(ConversationMessage(role="assistant", content=error_msg))

    return state


def _handle_edit(args: list[str], state: ConversationState, config: _Config) -> ConversationState:
    """
    Re-enter Q&A to modify existing draft.

    Args:
        args: Command arguments (draft ID)
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    if not args:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content="Error: /edit requires <draft-id>",
            )
        )
        return state

    draft_id = args[0]
    try:
        draft = load_draft(draft_id, config)
        state.mode = "task-create"
        state.active_draft_id = draft_id
        message = f"Editing draft: {draft_id}\n\nTitle: {draft.title}\n\nRe-enter Q&A to modify:"
        state.messages.append(ConversationMessage(role="assistant", content=message))
    except FileNotFoundError:
        error_msg = f"Error: Draft not found: {draft_id}"
        state.errors.append(error_msg)
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=error_msg,
            )
        )

    return state


def _handle_discard(
    args: list[str], state: ConversationState, config: _Config
) -> ConversationState:
    """
    Delete draft without creating task.

    Args:
        args: Command arguments (draft ID)
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    if not args:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content="Error: /discard requires <draft-id>",
            )
        )
        return state

    draft_id = args[0]
    try:
        delete_draft(draft_id, config)
        if draft_id in state.pending_enables:
            state.pending_enables.remove(draft_id)
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=f"Discarded draft: {draft_id}",
            )
        )
    except FileNotFoundError:
        error_msg = f"Error: Draft not found: {draft_id}"
        state.errors.append(error_msg)
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=error_msg,
            )
        )

    return state


def _handle_submit(state: ConversationState, config: _Config) -> ConversationState:
    """
    Review and submit batch of enabled drafts.

    Args:
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    if not state.pending_enables:
        error_msg = "Error: No drafts enabled. Use `/enable <draft-id>` first."
        state.errors.append(error_msg)
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=error_msg,
            )
        )
        return state

    summary = _prepare_batch_summary(state, config)
    summary_text = _display_batch_summary(summary)

    state.messages.append(
        ConversationMessage(
            role="assistant",
            content=f"{summary_text}\n\nConfirm submission? (confirm/reset)",
        )
    )

    state.active_draft_id = None
    return state


def _handle_reset(state: ConversationState, config: _Config) -> ConversationState:
    """
    Rollback entire session: delete created tasks, restore context.

    Args:
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    if not state.session_snapshot or not state.session_snapshot.created_task_ids:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content="Error: No tasks created in this session. Nothing to reset.",
            )
        )
        return state

    task_ids = state.session_snapshot.created_task_ids
    deleted_tasks = []
    for task_id in task_ids:
        try:
            _ = run_command_output(["bd", "delete", task_id])
            deleted_tasks.append(task_id)
        except SubprocessError:
            pass

    for filename, content in state.session_snapshot.initial_context_files.items():
        context_file_path = config.village_dir / "context" / filename
        context_file_path.parent.mkdir(parents=True, exist_ok=True)
        context_file_path.write_text(content, encoding="utf-8")

    state.pending_enables = []
    state.session_snapshot.created_task_ids = []
    state.active_draft_id = None

    state.messages.append(
        ConversationMessage(
            role="assistant",
            content=f"✓ Rolled back {len(deleted_tasks)} tasks\n\n"
            f"Context files restored.\n\n"
            f"Drafts preserved in `.village/drafts/` for recovery.",
        )
    )

    return state


def _handle_drafts(state: ConversationState, config: _Config) -> ConversationState:
    """
    List all draft tasks with status.

    Args:
        state: Current conversation state
        config: Village config

    Returns:
        Updated ConversationState
    """
    drafts = list_drafts(config)

    if not drafts:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content="No drafts found",
            )
        )
        return state

    lines = ["Draft tasks:\n"]
    for draft in drafts:
        enabled = "✓" if draft.id in state.pending_enables else " "
        lines.append(f"  [{enabled}] {draft.id} [{draft.scope}] {draft.title}")
        lines.append(f"      Created: {draft.created_at.strftime('%Y-%m-%d %H:%M')}")

    state.messages.append(
        ConversationMessage(
            role="assistant",
            content="\n".join(lines),
        )
    )

    return state


def _prepare_batch_summary(state: ConversationState, config: _Config) -> dict[str, Any]:
    """
    Prepare batch submission summary.

    Args:
        state: Current conversation state
        config: Village config

    Returns:
        Summary dict with tasks and context changes
    """
    drafts_info = []
    for draft_id in state.pending_enables:
        try:
            draft = load_draft(draft_id, config)
            drafts_info.append(
                {
                    "id": draft.id,
                    "title": draft.title,
                    "scope": draft.scope,
                    "estimate": draft.estimate,
                }
            )
        except FileNotFoundError:
            logger.warning(f"Draft not found: {draft_id}")

    context_changes = []
    for filename in state.context_diffs:
        context_changes.append(
            {
                "file": filename,
                "change": "modified",
            }
        )

    return {
        "total_tasks": len(drafts_info),
        "drafts": drafts_info,
        "context_changes": context_changes,
    }


def _display_batch_summary(summary: dict[str, Any]) -> str:
    """
    Display batch submission summary.

    Args:
        summary: Summary dict from _prepare_batch_summary

    Returns:
        Formatted summary string
    """
    lines = [
        "═══════════════════════════════════════════",
        "BATCH SUBMISSION REVIEW",
        "═══════════════════════════════════════════",
    ]

    if summary["drafts"]:
        lines.append("\nPENDING TASK ENABLES ({}):".format(summary["total_tasks"]))
        for draft in summary["drafts"]:
            lines.append(f'  • {draft["id"]} [{draft["scope"]}] "{draft["title"]}"')
    else:
        lines.append("\nNo tasks enabled for submission")

    if summary["context_changes"]:
        lines.append("\nCONTEXT CHANGES:")
        for change in summary["context_changes"]:
            lines.append(f"  • {change['file']}: {change['change']}")
    else:
        lines.append("\nNo context changes")

    lines.append("═══════════════════════════════════════════")
    return "\n".join(lines)


def should_exit(user_input: str) -> bool:
    """Check if user wants to exit."""
    return user_input.strip().lower() in {"/exit", "/quit", "/bye"}
