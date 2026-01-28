"""LLM chat session with task specification rendering."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from village.chat.task_spec import TaskSpec

if TYPE_CHECKING:
    from village.config import Config
    from village.llm.client import LLMClient

    _Config = Config
    _LLMClient = LLMClient
else:
    _Config = object
    _LLMClient = object

logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Chat session state."""

    current_task: TaskSpec | None = None
    refinements: list[str] = field(default_factory=list)


@dataclass
class LLMChat:
    """LLM chat session with task rendering and Beads API integration."""

    session: ChatSession
    llm_client: _LLMClient
    beads_client: _LLMClient | None = None

    def render_task_spec(self) -> str:
        """
        Render current task specification as ASCII box.

        Returns:
            Formatted task specification string
        """
        task = self.session.current_task
        if not task:
            return "No current task"

        box_width = 46
        lines = []

        lines.append("┌" + "─" * box_width + "┐")

        title_line = f" TASK: {task.title[:38]} "
        lines.append("│" + title_line + " " * (box_width - len(title_line)) + "│")

        lines.append("├" + "─" * box_width + "┤")

        title_text = f" Title: {task.title[:35]} "
        lines.append("│" + title_text + " " * (box_width - len(title_text)) + "│")

        scope_text = f" Scope: {task.scope:<35} "
        lines.append("│" + scope_text + " " * (box_width - len(scope_text)) + "│")

        estimate_text = f" Estimate: {task.estimate:<31} "
        lines.append("│" + estimate_text + " " * (box_width - len(estimate_text)) + "│")

        lines.append("├" + "─" * box_width + "┤")

        lines.append("│ DEPENDENCIES:" + " " * (box_width - 13) + "│")

        if task.blocked_by:
            blocked_str = str(task.blocked_by)[:33]
            blocked_line = f"   ⬇ BLOCKED BY: {blocked_str} "
            lines.append("│" + blocked_line + " " * (box_width - len(blocked_line)) + "│")
        else:
            lines.append("│" + " " * box_width + "│")

        if task.blocks:
            blocks_str = str(task.blocks)[:35]
            blocks_line = f"   ⬇ BLOCKS: {blocks_str} "
            lines.append("│" + blocks_line + " " * (box_width - len(blocks_line)) + "│")
        else:
            lines.append("│" + " " * box_width + "│")

        lines.append("├" + "─" * box_width + "┤")

        criteria_count = len(task.success_criteria)
        criteria_text = f" SUCCESS CRITERIA ({criteria_count}):"
        lines.append("│" + criteria_text + " " * (box_width - len(criteria_text)) + "│")

        for i, criteria in enumerate(task.success_criteria, 1):
            criteria_line = f"   {i}. {criteria[:40]} "
            lines.append("│" + criteria_line + " " * (box_width - len(criteria_line)) + "│")

        lines.append("├" + "─" * box_width + "┤")

        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        emoji = confidence_emoji[task.confidence]
        confidence_text = f" Confidence: {emoji} {task.confidence.upper():<30} "
        lines.append("│" + confidence_text + " " * (box_width - len(confidence_text)) + "│")

        lines.append("├" + "─" * box_width + "┤")

        lines.append("│ /refine /revise <clarification> - Revise   │")
        lines.append("│ /undo - Revert to previous version          │")
        lines.append("│ /confirm - Queue this task                   │")
        lines.append("│ /discard - Cancel                              │")

        lines.append("└" + "─" * box_width + "┘")

        return "\n".join(lines)

    def handle_help(self, topic: str | None = None) -> str:
        """
        Generate help text for chat commands.

        Args:
            topic: Optional help topic

        Returns:
            Help text string
        """
        base_help = """# Village Chat — Slash Commands

## Task Specification Commands
- `/refine <clarification>` — revise current task specification
- `/revise <clarification>` — alias for /refine
- `/undo` — revert to previous task specification version
- `/confirm` — queue current task for submission
- `/discard` — cancel current task specification

## General Commands
- `/tasks` — list Beads tasks
- `/task <id>` — show task details
- `/ready` — show ready tasks (Beads)
- `/status` — show Village status summary
- `/help [topic]` — show help

## Workflow
1. Create task specification via Q&A
2. Review rendered specification
3. Use `/refine` or `/revise` to iterate
4. `/confirm` when ready to queue
5. `/discard` to cancel
"""

        if topic:
            topic_lower = topic.lower()
            if topic_lower == "refine":
                return """## /refine Command

Refine the current task specification with additional clarification.

Usage: `/refine <clarification text>`

This command updates the task specification based on your feedback.
You can iterate multiple times until satisfied with the specification.

See also: /revise (alias)
"""
            elif topic_lower == "revise":
                return """## /revise Command

Revise the current task specification with additional clarification.

Usage: `/revise <clarification text>`

This is an alias for `/refine` - they are identical in functionality.

See also: /refine
"""
            elif topic_lower == "confirm":
                return """## /confirm Command

Confirm the current task specification and queue it for submission.

Usage: `/confirm`

The task will be added to the pending submission batch.
Use `/submit` to create the task in Beads.

See also: /submit, /discard
"""
            elif topic_lower == "undo":
                return """## /undo Command

Revert to the previous version of the task specification.

Usage: `/undo`

Each refinement creates a version history. Undo restores the
previous version.

See also: /refine, /revise
"""
            elif topic_lower == "discard":
                return """## /discard Command

Cancel the current task specification.

Usage: `/discard`

The current specification is discarded without creating a task.
Any refinements are lost.

See also: /confirm
"""
            else:
                return f"Unknown topic: {topic}\nAvailable: refine, revise, confirm, undo, discard"

        return base_help
