"""Task draft CRUD handlers for conversation mode."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from village.chat.drafts import (
    DraftTask,
    delete_draft,
    generate_draft_id,
    list_drafts,
    load_draft,
    save_draft,
)
from village.chat.state import (
    SessionSnapshot,
    save_session_state,
    take_session_snapshot,
)
from village.chat.task_extractor import TaskSubmissionSpec, create_draft_tasks, extract_task_specs
from village.tasks import TaskStoreError, get_task_store

if TYPE_CHECKING:
    from village.chat.conversation import ConversationState
    from village.config import Config

    _Config = Config
else:
    from village.config import Config as _Config  # type: ignore[misc]

logger = logging.getLogger(__name__)


def _error_reply(state: "ConversationState", message: str) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    state.errors.append(message)
    state.messages.append(ConversationMessage(role="assistant", content=message))
    return state


def handle_task_subcommand(
    state: "ConversationState", command: str, args: list[str], config: _Config
) -> "ConversationState":
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


def _switch_to_create_mode(args: list[str], state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

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
        f"Task creation mode enabled. Draft ID: {draft.id}\n\nStarting Q&A Phase 1: What is the goal of this task?"
    )
    state.messages.append(ConversationMessage(role="assistant", content=message))

    return state


def _handle_enable(args: list[str], state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    if not args:
        return _error_reply(state, "Error: /enable requires <draft-id> or 'all'")

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
            state = _error_reply(state, f"Error: Draft not found: {draft_id}")

    return state


def _handle_edit(args: list[str], state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    if not args:
        return _error_reply(state, "Error: /edit requires <draft-id>")

    draft_id = args[0]
    try:
        draft = load_draft(draft_id, config)
        state.mode = "task-create"
        state.active_draft_id = draft_id
        message = f"Editing draft: {draft_id}\n\nTitle: {draft.title}\n\nRe-enter Q&A to modify:"
        state.messages.append(ConversationMessage(role="assistant", content=message))
    except FileNotFoundError:
        state = _error_reply(state, f"Error: Draft not found: {draft_id}")

    return state


def _handle_discard(args: list[str], state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    if not args:
        return _error_reply(state, "Error: /discard requires <draft-id>")

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
        state = _error_reply(state, f"Error: Draft not found: {draft_id}")

    return state


def _handle_submit(state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    if not state.pending_enables:
        return _error_reply(state, "Error: No drafts enabled. Use `/enable <draft-id>` first.")

    from village.chat.state import load_session_state

    state_dict = load_session_state(config)

    try:
        breakdown = state_dict.get("session_snapshot", {}).get("task_breakdown", {})

        if breakdown and hasattr(breakdown, "items"):
            baseline = state_dict.get("session_snapshot", {}).get("brainstorm_baseline", {})
            config_git_root_name = config.git_root.name

            specs = extract_task_specs(
                baseline,
                breakdown,
                config_git_root_name,
            )
        else:
            specs = []
            for draft_id in state.pending_enables:
                try:
                    draft = load_draft(draft_id, config)
                    spec = TaskSubmissionSpec(
                        title=draft.title,
                        description=draft.description,
                        estimate=draft.estimate or "unknown",
                        success_criteria=[],
                        blockers=[],
                        depends_on=[],
                        batch_id="",
                        parent_task_id=None,
                        custom_fields={"scope": draft.scope} if draft.scope else {},
                    )
                    specs.append(spec)
                except FileNotFoundError:
                    logger.warning(f"Draft not found: {draft_id}")
                    continue

        if not specs:
            return _error_reply(state, "Error: No valid tasks to submit.")

        created_tasks = asyncio.run(create_draft_tasks(specs, config))
        created_ids = list(created_tasks.values())

        if state.session_snapshot is None:
            state.session_snapshot = SessionSnapshot(
                start_time=datetime.now(),
                batch_id="",
                initial_context_files={},
                current_context_files={},
                pending_enables=[],
                created_task_ids=[],
            )
        state.session_snapshot.created_task_ids = created_ids
        state.batch_submitted = True

        summary_text = f"Created {len(created_tasks)} task(s)"
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=summary_text,
            )
        )
        state.active_draft_id = None

        for draft_id in state.pending_enables:
            try:
                delete_draft(draft_id, config)
            except FileNotFoundError:
                pass
        state.pending_enables = []

        return state
    except Exception as e:
        logger.error(f"Failed to create tasks: {e}")
        state.errors.append(str(e))
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=f"Error creating tasks: {e}",
            )
        )
        return state


def _handle_reset(state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

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
    store = get_task_store(config=config)
    for task_id in task_ids:
        try:
            store.delete_task(task_id)
            deleted_tasks.append(task_id)
        except TaskStoreError:
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


def _handle_drafts(state: "ConversationState", config: _Config) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

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


def _prepare_batch_summary(state: "ConversationState", config: _Config) -> dict[str, Any]:
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
