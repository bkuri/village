"""Brainstorm workflow: break down tasks using Sequential Thinking."""

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from village.chat.baseline import collect_baseline
from village.chat.sequential_thinking import (
    generate_task_breakdown,
    validate_dependencies,
)
from village.chat.state import SessionSnapshot
from village.chat.task_extractor import create_draft_tasks, extract_task_specs
from village.tasks import TaskStoreError, get_task_store

if TYPE_CHECKING:
    from village.chat.conversation import ConversationState
    from village.config import Config

    _Config = Config
else:
    from village.config import Config as _Config  # type: ignore[misc]

logger = logging.getLogger(__name__)


async def handle_brainstorm(
    args: list[str],
    state: "ConversationState",
    config: _Config,
) -> "ConversationState":
    from village.chat.conversation import ConversationMessage

    try:
        initial_title = " ".join(args) if args else None
        baseline = collect_baseline(initial_title)

        snapshot_data = {
            "baseline_title": baseline.title,
            "baseline_reasoning": baseline.reasoning,
            "created_at": datetime.now().isoformat(),
        }

        state.session_snapshot = SessionSnapshot(
            start_time=datetime.now(),
            batch_id=f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            initial_context_files={},
            current_context_files={},
            pending_enables=[],
            created_task_ids=[],
            brainstorm_baseline=snapshot_data,
            brainstorm_created_ids=[],
        )

        try:
            store = get_task_store(config=config)
            all_tasks = store.list_tasks(limit=100)
            tasks_json = json.dumps([t.to_dict() for t in all_tasks])
        except TaskStoreError:
            tasks_json = None

        breakdown = generate_task_breakdown(
            baseline,
            config,
            tasks_state=tasks_json,
        )

        if not validate_dependencies(breakdown):
            state.messages.append(
                ConversationMessage(
                    role="assistant",
                    content=("Error: Task dependencies are invalid.\n\nTry: /brainstorm with simpler breakdown"),
                )
            )
            return state

        specs = extract_task_specs(
            baseline,
            breakdown,
            config.git_root.name,
        )

        created_tasks = await create_draft_tasks(specs, config)

        state.session_snapshot.brainstorm_created_ids = list(created_tasks.values())

        state.pending_enables.extend(state.session_snapshot.brainstorm_created_ids)

        for title, task_id in created_tasks.items():
            truncated = title[:48]
            state.messages.append(ConversationMessage(role="assistant", content=f"☐ {task_id}: {truncated}"))

        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=(
                    f"Created {len(created_tasks)} draft task"
                    f"{'s' if len(created_tasks) > 1 else ''}. "
                    "Next:\n"
                    f"  • /edit <id> to refine a task\n"
                    f"  • /enable <id> to add to submission batch\n"
                    f"  • /drafts to see all\n"
                    f"  • /submit when ready"
                ),
            )
        )

        return state

    except ValueError as e:
        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=f"Error: {str(e)}\n\nTry again with more details.",
            )
        )
        return state

    except Exception as e:
        if config.debug.enabled:
            logger.error(f"Brainstorm handler error: {e}")
        else:
            logger.error(f"Brainstorm handler error: {str(e)}")

        state.messages.append(
            ConversationMessage(
                role="assistant",
                content=(
                    "Error: Sequential Thinking couldn't break down task.\n\n"
                    "Try:\n"
                    "1. Simplify your description\n"
                    "2. Be more specific about what needs breaking down\n"
                    "3. Retry: /brainstorm [title]"
                ),
            )
        )
        return state
