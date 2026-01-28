"""LLM chat session with task specification rendering."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

from village.chat.beads_client import BeadsClient, BeadsError
from village.chat.task_spec import TaskSpec

ScopeType = Literal["fix", "feature", "config", "docs", "test", "refactor"]
ConfidenceType = Literal["high", "medium", "low"]

if TYPE_CHECKING:
    from village.config import Config
    from village.llm.client import LLMClient

    _Config = Config
    _LLMClient = LLMClient
else:
    _Config = object
    _LLMClient = object

logger = logging.getLogger(__name__)


SLASH_COMMANDS = {
    "/create": "handle_create",
    "/refine": "handle_refine",
    "/revise": "handle_refine",  # Alias for /refine
    "/undo": "handle_undo",
    "/confirm": "handle_confirm",
    "/discard": "handle_discard",
    "/tasks": "handle_tasks",
    "/task": "handle_task",
    "/ready": "handle_ready",
    "/status": "handle_status",
    "/history": "handle_history",
    "/help": "handle_help",
}


@dataclass
class ChatSession:
    """Chat session state."""

    current_task: TaskSpec | None = None
    refinements: list[dict[str, object]] = field(default_factory=list)
    current_iteration: int = 0  # 0 = original, 1+ = refinements

    def get_current_spec(self) -> TaskSpec | None:
        """Get latest task spec."""
        if self.current_iteration == 0:
            return self.current_task
        elif self.refinements:
            task_spec_dict = cast(dict[str, object], self.refinements[-1]["task_spec"])
            return TaskSpec(
                title=cast(str, task_spec_dict.get("title")),
                description=cast(str, task_spec_dict.get("description")),
                scope=cast(ScopeType, cast(str, task_spec_dict.get("scope"))),
                blocks=cast(list[str], task_spec_dict.get("blocks") or []),
                blocked_by=cast(list[str], task_spec_dict.get("blocked_by") or []),
                success_criteria=cast(list[str], task_spec_dict.get("success_criteria") or []),
                estimate=cast(str, task_spec_dict.get("estimate")),
                confidence=cast(
                    ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))
                ),
            )
        return self.current_task

    def add_refinement(self, task_spec: TaskSpec, user_input: str) -> None:
        """Add a refinement to history."""
        self.current_iteration += 1
        self.refinements.append(
            {
                "iteration": self.current_iteration,
                "task_spec": task_spec.__dict__,
                "user_input": user_input,
                "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop() else 0,
            }
        )
        self.current_task = task_spec

    def undo_refinement(self) -> bool:
        """Undo to previous refinement."""
        if self.current_iteration == 0:
            return False

        self.refinements.pop()
        self.current_iteration -= 1
        if self.refinements:
            task_spec_dict = cast(dict[str, object], self.refinements[-1]["task_spec"])
            self.current_task = TaskSpec(
                title=cast(str, task_spec_dict.get("title")),
                description=cast(str, task_spec_dict.get("description")),
                scope=cast(ScopeType, cast(str, task_spec_dict.get("scope"))),
                blocks=cast(list[str], task_spec_dict.get("blocks") or []),
                blocked_by=cast(list[str], task_spec_dict.get("blocked_by") or []),
                success_criteria=cast(list[str], task_spec_dict.get("success_criteria") or []),
                estimate=cast(str, task_spec_dict.get("estimate")),
                confidence=cast(
                    ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))
                ),
            )
        return True


@dataclass
class LLMChat:
    """LLM chat session with task rendering and Beads API integration."""

    session: ChatSession
    llm_client: _LLMClient
    beads_client: BeadsClient | None = None
    system_prompt: str | None = None

    def __init__(self, llm_client: _LLMClient, system_prompt: str | None = None) -> None:
        """Initialize LLM chat."""
        self.session = ChatSession()
        self.llm_client = llm_client
        self.beads_client = None
        self.system_prompt = system_prompt

    async def set_beads_client(self, beads_client: BeadsClient) -> None:
        """Set Beads client for task creation."""
        self.beads_client = beads_client

    async def handle_message(self, user_input: str) -> str:
        """
        Process user message and return response.

        Args:
            user_input: User's message

        Returns:
            Response string
        """
        user_input = user_input.strip()

        # Handle slash commands
        if user_input.startswith("/"):
            return await self.handle_slash_command(user_input)

        # Check if we have a current task or creating new one
        if self.session.current_task is None:
            return await self.handle_create(user_input)

        # If we have a task, user is refining/confirming/discard
        return await self.handle_refine(user_input)

    async def handle_slash_command(self, command: str) -> str:
        """Handle slash commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler_name = SLASH_COMMANDS.get(cmd)
        if not handler_name:
            return f"Unknown command: {cmd}\nUse /help for available commands"

        handler = getattr(self, handler_name)
        result = await handler(args) if asyncio.iscoroutinefunction(handler) else handler(args)
        return cast(str, result)

    async def handle_create(self, user_input: str) -> str:
        """Handle /create or natural language task creation."""
        logger.info(f"Creating task from input: {user_input[:50]}...")

        # Parse JSON response (type: ignore for Any return)
        response: str = self.llm_client.call(
            prompt=f"{user_input}\n\nParse this as a task specification. Extract any dependencies (blocks X, blocked by Y). Return JSON only.",
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        import json

        try:
            task_spec_dict = json.loads(response)
        except json.JSONDecodeError:
            return f"Failed to parse LLM response. Got: {response[:100]}"

        # Validate required fields
        required_fields = ["title", "description", "scope"]
        missing_fields = [f for f in required_fields if f not in task_spec_dict]
        if missing_fields:
            return f"Missing required fields: {', '.join(missing_fields)}\nPlease provide: title, description, scope"

        # Set defaults
        task_spec_dict.setdefault("blocks", [])
        task_spec_dict.setdefault("blocked_by", [])
        task_spec_dict.setdefault("success_criteria", [])
        task_spec_dict.setdefault("estimate", "unknown")
        task_spec_dict.setdefault("confidence", "medium")

        # Create TaskSpec
        task_spec = TaskSpec(
            title=task_spec_dict["title"],
            description=task_spec_dict["description"],
            scope=task_spec_dict["scope"],
            blocks=task_spec_dict["blocks"],
            blocked_by=task_spec_dict["blocked_by"],
            success_criteria=task_spec_dict["success_criteria"],
            estimate=task_spec_dict["estimate"],
            confidence=task_spec_dict["confidence"],
        )

        # Store in session
        self.session.current_task = task_spec
        self.session.current_iteration = 0
        self.session.refinements = []

        logger.info(f"Task spec created: {task_spec.title}")

        return self.render_task_spec(task_spec)

    async def handle_refine(self, user_input: str) -> str:
        """Handle /refine or /revise command."""
        if not self.session.current_task:
            return "No current task to refine. Use /create to start a new task."

        logger.info(f"Refining task with input: {user_input[:50]}...")

        # Parse refinement with LLM
        current_spec = self.session.get_current_spec()
        if not current_spec:
            return "No current task specification."

        response = self.llm_client.call(
            prompt=f"Current task:\n{self._task_spec_to_text(current_spec)}\n\nUser refinement: {user_input}\n\nUpdate the task specification based on this feedback. Preserve as much as possible, only change what the refinement explicitly addresses. Extract any new dependencies. Return JSON only.",
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        # Parse JSON response
        import json

        try:
            refined_dict = json.loads(response)
        except json.JSONDecodeError as e:
            return f"Failed to parse refinement. Got: {e}\nGot: {response[:100]}"

        # Set defaults
        refined_dict.setdefault("blocks", current_spec.blocks)
        refined_dict.setdefault("blocked_by", current_spec.blocked_by)
        refined_dict.setdefault("success_criteria", current_spec.success_criteria)
        refined_dict.setdefault("estimate", current_spec.estimate)
        refined_dict.setdefault("confidence", current_spec.confidence)

        # Create refined TaskSpec
        refined_spec = TaskSpec(
            title=refined_dict["title"],
            description=refined_dict["description"],
            scope=refined_dict["scope"],
            blocks=refined_dict["blocks"],
            blocked_by=refined_dict["blocked_by"],
            success_criteria=refined_dict["success_criteria"],
            estimate=refined_dict["estimate"],
            confidence=refined_dict["confidence"],
        )

        # Add refinement to session
        self.session.add_refinement(refined_spec, user_input)

        summary = refined_dict.get("refinement_summary", "Updated based on feedback")
        logger.info(
            f"Task refined (iteration {self.session.current_iteration}): {refined_spec.title} - {summary}"
        )

        return self.render_task_spec(refined_spec, self.session.current_iteration)

    async def handle_undo(self, args: str) -> str:
        """Handle /undo command."""
        if not self.session.undo_refinement():
            return "❌ Nothing to undo (at original task)"

        previous_spec = self.session.get_current_spec()
        if previous_spec:
            logger.info(f"Undid to refinement #{self.session.current_iteration}")
            return f"↩️ Reverted to Refinement #{self.session.current_iteration}\n\n{self.render_task_spec(previous_spec, self.session.current_iteration)}"
        return "↩️ Reverted to original task"

    async def handle_confirm(self, args: str) -> str:
        """Handle /confirm command."""
        if not self.beads_client:
            return "Beads client not configured. Cannot create task."

        spec = self.session.get_current_spec()
        if not spec:
            return "No current task to confirm. Use /create to start a new task."

        logger.info(f"Confirming task: {spec.title}")

        try:
            task_id = await self.beads_client.create_task(spec)
            return f"✓ Task created: {task_id}\n\nDependencies: {spec.dependency_summary()}\n\nReady to queue with: village queue --agent {spec.scope}"
        except BeadsError as e:
            logger.error(f"Failed to create task: {e}")
            return f"❌ Failed to create task: {e}"

    async def handle_discard(self, args: str) -> str:
        """Handle /discard command."""
        if not self.session.current_task:
            return "No current task to discard."

        task_title = self.session.current_task.title if self.session.current_task else "task"
        self.session.current_task = None
        self.session.current_iteration = 0
        self.session.refinements = []

        logger.info(f"Discarded task: {task_title}")
        return f"🗑️ Task '{task_title}' discarded. Use /create to start a new task."

    async def handle_tasks(self, args: str) -> str:
        """Handle /tasks command - list Beads tasks."""
        if not self.beads_client:
            return "Beads client not configured."

        try:
            tasks = await self.beads_client.search_tasks(query="", limit=10, status="open")
            if not tasks:
                return "No open tasks found."

            lines = ["\n📋 OPEN TASKS (last 10):\n"]
            for task in tasks:
                lines.append(f"  • {task.get('id', 'N/A')} - {task.get('title', 'N/A')}")

            return "\n".join(lines)
        except BeadsError as e:
            logger.error(f"Failed to list tasks: {e}")
            return f"❌ Failed to list tasks: {e}"

    async def handle_task(self, args: str) -> str:
        """Handle /task <id> command - show task details."""
        if not self.beads_client or not args:
            return "Usage: /task <task-id>"

        task_id = args.strip()
        if not task_id:
            return "Usage: /task <task-id>"

        try:
            deps = await self.beads_client.get_dependencies(task_id)
            if not deps:
                return f"Task {task_id} has no dependencies."

            lines = [f"\n📋 TASK: {task_id}\n", "DEPENDENCIES:\n"]
            for dep_type, task_list in deps.items():
                if isinstance(task_list, list):
                    lines.append(
                        f"  {dep_type}: {', '.join(cast(list[str], task_list)) if task_list else '(none)'}"
                    )
                else:
                    lines.append(f"  {dep_type}: {task_list}")

            return "\n".join(lines)
        except BeadsError as e:
            logger.error(f"Failed to get task dependencies: {e}")
            return f"❌ Failed to get dependencies: {e}"

    async def handle_ready(self, args: str) -> str:
        """Handle /ready command - show ready tasks."""
        if not self.beads_client:
            return "Beads client not configured."

        try:
            ready_tasks = await self.beads_client.search_tasks(query="", limit=10, status="ready")
            if not ready_tasks:
                return "No ready tasks found."

            lines = ["\n✅ READY TASKS (last 10):\n"]
            for task in ready_tasks:
                lines.append(f"  • {task.get('id', 'N/A')} - {task.get('title', 'N/A')}")

            return "\n".join(lines)
        except BeadsError as e:
            logger.error(f"Failed to list ready tasks: {e}")
            return f"❌ Failed to list ready tasks: {e}"

    async def handle_status(self, args: str) -> str:
        """Handle /status command - show chat session status."""
        if self.session.current_task:
            spec = self.session.get_current_spec()
            if spec is None:
                return "\n📋 CURRENT SESSION:\n  No active task\n"
            lines = [
                "\n📋 CURRENT SESSION:\n",
                f"  Task: {spec.title}\n",
                f"  Refinements: {self.session.current_iteration}\n",
                f"  Scope: {spec.scope}\n",
                f"  Dependencies: {spec.dependency_summary()}\n",
                "  Status: Pending /confirm\n",
            ]
            return "\n".join(lines)
        else:
            return "\n📋 CURRENT SESSION:\n  No active task\n"

    async def handle_history(self, args: str) -> str:
        """Handle /history command - show refinement history."""
        if not self.session.refinements:
            return "No refinement history yet."

        lines = ["\n📝 REFINEMENT HISTORY:\n"]
        for ref in self.session.refinements:
            task_spec_dict = cast(dict[str, object], ref["task_spec"])
            task_spec = TaskSpec(
                title=cast(str, task_spec_dict.get("title")),
                description=cast(str, task_spec_dict.get("description")),
                scope=cast(ScopeType, cast(str, task_spec_dict.get("scope"))),
                blocks=cast(list[str], task_spec_dict.get("blocks") or []),
                blocked_by=cast(list[str], task_spec_dict.get("blocked_by") or []),
                success_criteria=cast(list[str], task_spec_dict.get("success_criteria") or []),
                estimate=cast(str, task_spec_dict.get("estimate")),
                confidence=cast(
                    ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))
                ),
            )
            lines.append(f"  #{ref['iteration']}: {task_spec.title}")
            lines.append(f"     User: {ref['user_input']}")
            lines.append(f"     {task_spec.scope} - {task_spec.estimate}")

        return "\n".join(lines)

    def handle_help(self, args: str) -> str:
        """Handle /help command."""
        return """
# Village Chat — Slash Commands

## Task Specification Commands
  /create <task description>  — Create new task (natural language)
  /refine <clarification>   — Refine current task
  /revise <clarification>   — Alias for /refine (identical)
  /undo                     — Revert to previous version
  /confirm                  — Queue current task in Beads
  /discard                  — Cancel current task

## Beads Query Commands
  /tasks                    — List open Beads tasks
  /task <id>               — Show task details and dependencies
  /ready                    — Show ready (unblocked) tasks

## Session Commands
  /status                   — Show current session state
  /history                  — Show refinement history
  /help [topic]            — This help message

## Workflow
  1. Describe task in natural language
  2. Review rendered specification
  3. Use /refine or /revise to iterate
  4. Use /confirm when ready to queue
  5. Use /undo to revert refinements

## Examples
  /create I need to fix the login bug
  /refine It blocks the dashboard widget
  /revise Actually, it blocks the profile page
  /undo
  /confirm
  /discard

## Dependencies
Village automatically detects dependencies from your input:
  • "blocks X" → Task will block X
  • "blocked by Y" → Task is blocked by Y
  • "depends on Z" → Task depends on Z

Use exact Beads IDs (e.g., bd-abc123) for best results.
"""

    def render_task_spec(self, spec: TaskSpec, refinement_count: int = 0) -> str:
        """Render task specification as ASCII box with dependencies."""
        box_width = 46
        lines = []

        lines.append("┌" + "─" * box_width + "┐")
        title_display = (
            f"{spec.title} (Refinement #{refinement_count})" if refinement_count > 0 else spec.title
        )
        lines.append("│" + f" TASK: {title_display[:38]} " + " " * (box_width - 39) + "│")
        lines.append("├" + "─" * box_width + "┤")
        lines.append("│" + f" Title: {spec.title[:35]} " + " " * (box_width - 35) + "│")
        lines.append("│" + f" Scope: {spec.scope:<35} " + " " * (box_width - 35) + "│")
        lines.append("│" + f" Estimate: {spec.estimate:<31} " + " " * (box_width - 31) + "│")
        lines.append("├" + "─" * box_width + "┤")

        # Dependencies section
        if spec.has_dependencies():
            lines.append("│" + " DEPENDENCIES: " + " " * (box_width - 13) + "│")

            if spec.blocked_by:
                blocked_str = ", ".join(spec.blocked_by)[:30]
                lines.append(
                    "│" + f"   ⬇ BLOCKED BY: {blocked_str} " + " " * (box_width - 42) + "│"
                )
            else:
                lines.append("│" + " " * box_width + "│")

            if spec.blocks:
                blocks_str = ", ".join(spec.blocks)[:33]
                lines.append("│" + f"   ⬇ BLOCKS: {blocks_str} " + " " * (box_width - 41) + "│")
            else:
                lines.append("│" + " " * box_width + "│")
        else:
            lines.append("│" + " DEPENDENCIES: (none) " + " " * (box_width - 19) + "│")

        lines.append("├" + "─" * box_width + "┤")
        lines.append(
            "│"
            + f" SUCCESS CRITERIA ({len(spec.success_criteria)}): "
            + " " * (box_width - 23)
            + "│"
        )

        for i, criterion in enumerate(spec.success_criteria, 1):
            lines.append("│" + f"   {i}. {criterion[:40]} " + " " * (box_width - 41) + "│")

        lines.append("├" + "─" * box_width + "┤")

        # Confidence indicator
        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        emoji = confidence_emoji[spec.confidence]
        lines.append(
            "│"
            + f" Confidence: {emoji} {spec.confidence.upper():<30} "
            + " " * (box_width - 41)
            + "│"
        )
        lines.append("├" + "─" * box_width + "┤")

        # Commands
        lines.append(
            "│"
            + " /refine /revise <clarification> - Revise this task      "
            + " " * (box_width - 55)
            + "│"
        )
        lines.append(
            "│"
            + " /undo - Revert to previous version                     "
            + " " * (box_width - 50)
            + "│"
        )
        lines.append(
            "│"
            + " /confirm - Queue this task                              "
            + " " * (box_width - 50)
            + "│"
        )
        lines.append(
            "│"
            + " /discard - Cancel                                       "
            + " " * (box_width - 43)
            + "│"
        )
        lines.append("└" + "─" * box_width + "┘")

        return "\n".join(lines)

    def _task_spec_to_text(self, spec: TaskSpec) -> str:
        """Convert TaskSpec to text for LLM prompt."""
        lines = [
            f"Title: {spec.title}",
            f"Description: {spec.description}",
            f"Scope: {spec.scope}",
            f"Blocks: {', '.join(spec.blocks) if spec.blocks else '(none)'}",
            f"Blocked by: {', '.join(spec.blocked_by) if spec.blocked_by else '(none)'}",
            f"Success Criteria: {', '.join(spec.success_criteria) if spec.success_criteria else '(none)'}",
        ]
        return "\n".join(lines)

    def _get_prompt(self) -> str:
        """Get system prompt for LLM."""
        return """You are a Task Specification Agent for Village.

Your job: Parse conversational input into structured PPC contracts with explicit Beads task IDs for dependencies.

## Dependency Detection Rules

When user mentions dependencies, you MUST:

### Option 1: Use Exact Beads ID
If user says "bd-abc123" or mentions "bd-abc123", use that exact ID:
{
  "blocks": ["bd-abc123"],
  "blocked_by": []
}

### Option 2: Use Task Name Pattern
If user says "blocks the dashboard widget", use pattern:
{
  "blocks": ["dashboard-widget"],
  "blocked_by": []
}

**Important**: These patterns will be resolved to actual Beads IDs by Village after you return the spec.

### Option 3: Ambiguous Reference (Ask for Clarification)
If user says "blocks it" without specifying which task:
{
  "needs_clarification": true,
  "clarification_question": "You mentioned 'blocks it' - which specific task does this block?",
  "suggested_tasks": [
    {"id": "dashboard-widget", "title": "Update dashboard widget"},
    {"id": "profile-page", "title": "Update user profile page"}
  ]
}

## Dependency Patterns to Detect

| Pattern | Meaning | Beads Format |
|----------|----------|----------------|
| "blocks X" | Current task blocks X | `blocks: [X]` |
| "blocked by Y" | Blocked by Y | `blocked_by: [Y]` |
| "depends on Z" | Depends on Z | `blocked_by: [Z]` |
| "cannot start until A" | Requires A to complete | `blocked_by: [A]` |

## Output Format

### Valid Task Spec
{
  "title": "Task title",
  "description": "Detailed description",
  "scope": "fix|feature|config|docs|test|refactor",
  "blocks": ["task-id-1", "task-id-2"],
  "blocked_by": ["task-id-3", "task-id-4"],
  "success_criteria": ["Criterion 1", "Criterion 2", "Criterion 3"],
  "estimate": "X-Y hours|days|weeks",
  "confidence": "high|medium|low"
}

### Ambiguous Input (Needs Clarification)
{
  "needs_clarification": true,
  "clarification_question": "What specific task does this block?",
  "suggested_tasks": [
    {"id": "task-id-1", "title": "Task 1 title"},
    {"id": "task-id-2", "title": "Task 2 title"}
  ],
  "partial_spec": {...}
}

## Transparency Requirements

**ALWAYS explain to user:**
1. What dependencies you extracted
2. Why you interpreted it that way
3. If you're unsure, ask for clarification

Be concise and focused on task specification only."""
