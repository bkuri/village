"""LLM chat session with task specification rendering."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional, cast

from village.chat.sequential_thinking import (
    TaskBreakdown,
)
from village.chat.task_spec import TaskSpec
from village.extensibility import ExtensionRegistry
from village.extensibility.context import SessionContext
from village.extensibility.task_hooks import TaskCreated
from village.extensibility.thinking_refiners import QueryRefinement
from village.extensibility.tool_invokers import ToolInvocation, ToolResult
from village.tasks import TaskCreate, TaskStore, TaskStoreError, get_task_store

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
    "/reset": "handle_discard",  # Alias for /discard
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
    current_breakdown: TaskBreakdown | None = None
    query_refinement: QueryRefinement | None = None

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
                confidence=cast(ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))),
                search_hints=cast(dict[str, list[str]], task_spec_dict.get("search_hints") or {}),
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
                "timestamp": time.time(),
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
                confidence=cast(ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))),
                search_hints=cast(dict[str, list[str]], task_spec_dict.get("search_hints") or {}),
            )
        return True


@dataclass
class LLMChat:
    """LLM chat session with task rendering and extension hooks.

    Supports domain-specific customization through ExtensionRegistry hooks:
    - ChatProcessor: Pre/post message processing
    - ToolInvoker: Customize MCP tool invocation
    - ThinkingRefiner: Domain-specific query refinement
    - ChatContext: Session state/context management
    - TaskHooks: Customize task creation/updates
    """

    session: ChatSession
    llm_client: _LLMClient
    extensions: ExtensionRegistry
    system_prompt: str | None = None
    config: _Config | None = None
    session_id: str = field(default="")
    session_context: SessionContext | None = None

    def __init__(
        self,
        llm_client: _LLMClient,
        system_prompt: str | None = None,
        config: _Config | None = None,
        extensions: Optional[ExtensionRegistry] = None,
    ) -> None:
        """Initialize LLM chat.

        Args:
            llm_client: LLM client for API calls
            system_prompt: System prompt for LLM
            config: Village configuration
            extensions: Extension registry for domain-specific customization
        """
        self.session = ChatSession()
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.config = config
        self.extensions = extensions or ExtensionRegistry()
        self.session_id = str(uuid.uuid4())
        self.session_context = None

    def _get_store(self) -> "TaskStore":
        """Get task store instance from config."""
        if self.config is None:
            raise TaskStoreError("Config not available")
        return get_task_store(config=self.config)

    async def set_extensions(self, extensions: ExtensionRegistry) -> None:
        """Set extension registry."""
        self.extensions = extensions

    async def _call_llm_with_retry(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """Call LLM with retry logic from LLMProviderAdapter.

        Args:
            prompt: User prompt for LLM
            system_prompt: Optional system prompt
            max_retries: Maximum retry attempts

        Returns:
            LLM response string

        Raises:
            Exception: If all retries fail
        """
        adapter = self.extensions.get_llm_adapter()
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return self.llm_client.call(
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            except Exception as e:
                last_error = e
                if not await adapter.should_retry(e):
                    raise
                if attempt < max_retries - 1:
                    delay = await adapter.get_retry_delay(attempt + 1)
                    logger.warning(f"LLM call failed (attempt {attempt + 1}), retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)

        raise last_error or Exception("LLM call failed after retries")

    async def handle_message(self, user_input: str) -> str:
        """
        Process user message and return response.

        Args:
            user_input: User's message

        Returns:
            Response string
        """
        user_input = user_input.strip()

        processor = self.extensions.get_processor()
        chat_context = self.extensions.get_chat_context()

        # Load context if not already loaded
        if self.session_context is None:
            self.session_context = await chat_context.load_context(self.session_id)

        # Handle slash commands BEFORE pre-processing (to preserve command detection)
        if user_input.startswith("/"):
            response = await self.handle_slash_command(user_input)
        else:
            # Apply pre-processing hook (domain-specific input normalization)
            user_input = await processor.pre_process(user_input)

            # Enrich context with domain-specific data
            self.session_context = await chat_context.enrich_context(self.session_context)

            # Apply domain-specific query refinement
            refiner = self.extensions.get_thinking_refiner()
            if await refiner.should_refine(user_input):
                self.session.query_refinement = await refiner.refine_query(user_input)
                logger.info(f"Query refined into {len(self.session.query_refinement.refined_steps)} steps")

            # Check if we have a current task or creating new one
            if self.session.current_task is None:
                response = await self.handle_create(user_input)
            # If we have a task, user is refining/confirming/discard
            else:
                response = await self.handle_refine(user_input)

        # Save context after processing
        if self.session_context:
            await chat_context.save_context(self.session_context)

        # Apply post-processing hook (domain-specific output formatting)
        response = await processor.post_process(response)
        return response

    async def invoke_tool(self, tool_name: str, args: dict[str, object]) -> ToolResult:
        """Invoke an MCP tool with ToolInvoker customization hooks.

        This is a hook point for future MCP tool integration. When the chat loop
        needs to call MCP tools (e.g., for context enrichment, external API calls,
        or domain-specific operations), use this method to allow domains to customize:

        - should_invoke(): Filter/allow tool calls based on domain rules
        - transform_args(): Modify arguments before invocation (e.g., inject context)
        - on_success(): Post-process results, cache, log metrics
        - on_error(): Handle failures, fallback strategies

        Example future usage in handle_message():
            # Fetch additional context from external tools
            result = await self.invoke_tool("fetch_docs", {"url": doc_url})
            if result.success:
                context = result.result

        Args:
            tool_name: Name of the MCP tool to invoke
            args: Arguments to pass to the tool

        Returns:
            ToolResult with success status, result data, and optional error
        """
        invoker = self.extensions.get_tool_invoker()
        invocation = ToolInvocation(
            tool_name=tool_name,
            args=args,
            context={"session_id": self.session_id},
        )

        if not await invoker.should_invoke(invocation):
            return ToolResult(success=False, result=None, error="Tool invocation skipped by domain filter")

        transformed_args = await invoker.transform_args(invocation)

        try:
            # TODO: Wire to actual MCP tool invocation when integrated
            # result = await self.mcp_client.call_tool(tool_name, transformed_args)
            # For now, return placeholder indicating hook infrastructure is ready
            result = {"tool_name": tool_name, "args": transformed_args, "status": "hook_ready"}
            processed_result = await invoker.on_success(invocation, result)
            return ToolResult(success=True, result=processed_result)
        except Exception as e:
            await invoker.on_error(invocation, e)
            return ToolResult(success=False, result=None, error=str(e))

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

        # Build prompt with refined steps if available
        if self.session.query_refinement:
            refined_steps_text = "\n".join(
                f"{i + 1}. {step}" for i, step in enumerate(self.session.query_refinement.refined_steps)
            )
            prompt = (
                f"Original user query: {user_input}\n\n"
                f"Domain-specific analysis steps:\n{refined_steps_text}\n\n"
                f"Context hints: {self.session.query_refinement.context_hints}\n\n"
                "Parse this as a task specification. Extract any dependencies "
                "(blocks X, blocked by Y). Return JSON only."
            )
            logger.info("Using refined steps for task creation")
        else:
            prompt = (
                f"{user_input}\n\n"
                "Parse this as a task specification. Extract any dependencies "
                "(blocks X, blocked by Y). Return JSON only."
            )

        # Parse JSON response
        response: str = await self._call_llm_with_retry(
            prompt=prompt,
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        try:
            json_text = response.strip()
            if json_text.startswith("```"):
                json_text = json_text.split("```")[1] if "```" in json_text[3:] else json_text
                if json_text.startswith("json"):
                    json_text = json_text[4:]
            task_spec_dict = json.loads(json_text.strip())
        except json.JSONDecodeError:
            return f"Failed to parse LLM response. Got: {response[:200]}"

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
            search_hints=task_spec_dict.get("search_hints", {}),
        )

        # Store in session
        self.session.current_task = task_spec
        self.session.current_iteration = 0
        self.session.refinements = []
        self.session.query_refinement = None

        logger.info(f"Task spec created: {task_spec.title}")

        # Check if task should be decomposed
        should_decompose, reasoning = await self._should_decompose(task_spec)

        if should_decompose:
            logger.info(f"Task '{task_spec.title}' identified as complex. Offering decomposition. Reason: {reasoning}")
            return await self._offer_decomposition(task_spec, user_input)

        return self.render_task_spec(task_spec)

    async def _should_decompose(self, task_spec: TaskSpec) -> tuple[bool, str]:
        """
        Ask LLM if task should be decomposed into smaller subtasks.

        Uses semantic understanding instead of brittle keyword matching.

        Args:
            task_spec: The task specification to evaluate

        Returns:
            Tuple of (should_decompose: bool, reasoning: str)
        """
        prompt = f"""Given this task:
Title: {task_spec.title}
Description: {task_spec.description}
Scope: {task_spec.scope}
Estimate: {task_spec.estimate}

Should this task be decomposed into smaller subtasks?

Consider:
- Can it be completed in one focused session (2-4 hours)?
- Are there natural boundaries or phases?
- Would parallel work by multiple developers help?
- Are there distinct deliverables?
- Is the description vague or broad?

Return JSON with format: {{"should_decompose": true/false, "reasoning": "brief explanation"}}"""

        try:
            response: str = await self._call_llm_with_retry(
                prompt=prompt,
                system_prompt=(
                    "You are a task analysis expert. Determine if tasks should be broken down into smaller pieces."
                ),
            )

            result = json.loads(response)

            should_decompose = result.get("should_decompose", False)
            reasoning = result.get("reasoning", "No reasoning provided")

            return should_decompose, reasoning

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"Failed to parse complexity detection response: {e}")
            # Default to not decomposing on error
            return False, f"Error in complexity detection: {e}"

    async def _offer_decomposition(self, task_spec: TaskSpec, user_input: str) -> str:
        """
        Generate task breakdown using Sequential Thinking.

        Creates BaselineReport from task_spec, calls generate_task_breakdown(),
        validates dependencies, and stores in session.

        Args:
            task_spec: The task specification to decompose
            user_input: Original user input for context

        Returns:
            Rendered breakdown or error message
        """
        from village.chat.baseline import BaselineReport
        from village.chat.sequential_thinking import generate_task_breakdown, validate_dependencies

        if not self.config:
            return "❌ Config not available. Cannot generate breakdown."

        try:
            # Create baseline report from task spec
            baseline = BaselineReport(
                title=task_spec.title,
                reasoning=f"Task decomposition requested for: {task_spec.description[:100]}...",
                parent_task_id=None,
            )

            # Generate breakdown using Sequential Thinking
            breakdown = generate_task_breakdown(
                baseline=baseline,
                config=self.config,
                tasks_state=None,  # Could pass current task state for context
                llm_client=self.llm_client,
            )

            # Validate dependencies
            if not validate_dependencies(breakdown):
                return self._render_decomposition_error(
                    error_message="Generated breakdown has invalid dependencies",
                    task_info=f"Title: {task_spec.title}",
                    breakdown=self._breakdown_to_text(breakdown),
                    offer_retry=True,
                )

            # Store in session
            self.session.current_breakdown = breakdown
            self.session.current_task = task_spec  # Keep original for reference

            logger.info(f"Generated breakdown with {len(breakdown.items)} subtasks")

            # Render and return
            return self._render_breakdown(breakdown)

        except Exception as e:
            logger.error(f"Failed to generate breakdown: {e}")
            return self._render_decomposition_error(
                error_message=f"Failed to generate task breakdown: {e}",
                task_info=f"Title: {task_spec.title}\nDescription: {task_spec.description[:100]}...",
                offer_retry=True,
            )

    def _render_breakdown(self, breakdown: TaskBreakdown) -> str:
        """Render TaskBreakdown as ASCII table."""
        box_width = 46
        lines = []

        title_display = breakdown.title_original or "Untitled"
        if breakdown.title_suggested:
            title_display += f" → {breakdown.title_suggested}"

        lines.append("┌" + "─" * box_width + "┐")
        lines.append("│" + f" BREAKDOWN: {title_display[:40]} " + " " * (box_width - 49) + "│")
        lines.append("├" + "─" * box_width + "┤")

        # Build index → title map
        index_to_title = {i: item.title for i, item in enumerate(breakdown.items)}

        for i, item in enumerate(breakdown.items, 1):
            # Map dependency indices to titles
            if item.dependencies:
                deps_str = ", ".join(index_to_title.get(d, f"#{d}") for d in item.dependencies)
            else:
                deps_str = "none"

            # Title truncated
            title_short = item.title[:35]

            lines.append("│" + f" {i}. {title_short}" + " " * (box_width - 40) + "│")

            # Description (2 lines max)
            desc_words = item.description.split()[:8]
            desc_short = " ".join(desc_words)
            lines.append("│" + f"    {desc_short}" + " " * (box_width - 45) + "│")

            # Dependencies and effort
            lines.append("│" + f"    [depends: {deps_str}]" + " " * (box_width - 22) + "│")
            lines.append("│" + f"    [effort: {item.estimated_effort}]" + " " * (box_width - 20) + "│")

            if i < len(breakdown.items):
                lines.append("│" + " " * box_width + "│")

        lines.append("└" + "─" * box_width + "┘")

        # Action hints
        lines.append("")
        lines.append("Actions:")
        lines.append("  /confirm   Create all subtasks in task store")
        lines.append("  /edit      Refine entire breakdown")
        lines.append("  /discard    Cancel this breakdown")

        return "\n".join(lines)

    def _breakdown_to_text(self, breakdown: TaskBreakdown) -> str:
        """Convert TaskBreakdown to text for LLM prompt."""
        lines = [f"Title: {breakdown.title_original or 'Untitled'}"]

        if breakdown.summary:
            lines.append(f"Summary: {breakdown.summary}")

        lines.append("Subtasks:")
        for i, item in enumerate(breakdown.items, 1):
            deps_str = ", ".join(str(d) for d in item.dependencies) if item.dependencies else "none"
            lines.append(f"  {i}. {item.title}")
            lines.append(f"     {item.description}")
            lines.append(f"     [depends: {deps_str}] [effort: {item.estimated_effort}]")

        return "\n".join(lines)

    async def handle_refine(self, user_input: str) -> str:
        """
        Handle /refine or /edit command.

        Works for BOTH:
        - Single task (existing behavior)
        - Breakdown (new: modifies entire breakdown)
        """
        # Case 1: Refine breakdown
        if self.session.current_breakdown:
            return await self._refine_breakdown(user_input)

        # Case 2: Refine single task (existing behavior)
        if not self.session.current_task:
            return "❌ No current task or breakdown to refine. Use /create to start a new task."

        logger.info(f"Refining task with input: {user_input[:50]}...")

        # Parse refinement with LLM (existing code)
        current_spec = self.session.get_current_spec()
        if not current_spec:
            return "❌ No current task specification."

        response = await self._call_llm_with_retry(
            prompt=(
                f"Current task:\n{self._task_spec_to_text(current_spec)}\n\n"
                f"User refinement: {user_input}\n\n"
                "Update task specification based on this feedback. "
                "Preserve as much as possible, only change what refinement explicitly addresses. "
                "Extract any new dependencies. Return JSON only."
            ),
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        # Parse JSON response
        import json

        try:
            refined_dict = json.loads(response)
        except json.JSONDecodeError as e:
            return f"❌ Failed to parse refinement. Got: {e}\nGot: {response[:100]}"

        # Set defaults (existing code)
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
            search_hints=refined_dict.get("search_hints", {}),
        )

        # Add refinement to session
        self.session.add_refinement(refined_spec, user_input)

        summary = refined_dict.get("refinement_summary", "Updated based on feedback")
        logger.info(f"Task refined (iteration {self.session.current_iteration}): {refined_spec.title} - {summary}")

        return self.render_task_spec(refined_spec, self.session.current_iteration)

    async def handle_undo(self, args: str) -> str:
        """Handle /undo command."""
        if not self.session.undo_refinement():
            return "❌ Nothing to undo (at original task)"

        previous_spec = self.session.get_current_spec()
        if previous_spec:
            logger.info(f"Undid to refinement #{self.session.current_iteration}")
            return (
                f"↩️ Reverted to Refinement #{self.session.current_iteration}\n\n"
                f"{self.render_task_spec(previous_spec, self.session.current_iteration)}"
            )
        return "↩️ Reverted to original task"

    async def handle_confirm(self, args: str) -> str:
        """
        Handle /confirm command.

        Works for BOTH:
        - Single task (existing behavior)
        - Breakdown (new: creates all subtasks)
        """
        # Case 1: Confirm breakdown (create all subtasks)
        if self.session.current_breakdown:
            return await self._confirm_breakdown()

        # Case 2: Confirm single task (existing behavior)
        spec = self.session.get_current_spec()
        if not spec:
            return "❌ No current task to confirm. Use /create to start a new task."

        logger.info(f"Confirming task: {spec.title}")

        integrator = self.extensions.get_task_hooks()
        context = {
            "task_spec": spec,
            "session_id": self.session_id,
            "session_context": self.session_context,
        }

        try:
            store = self._get_store()
            bump_label = f"bump:{spec.bump}" if spec.bump and spec.bump != "none" else None
            labels: list[str] = []
            if bump_label:
                labels.append(bump_label)

            task_create = TaskCreate(
                title=spec.title,
                description=spec.description,
                issue_type=spec.scope if spec.scope in ("bug", "feature", "chore", "epic") else "task",
                priority=2,
                labels=labels,
                depends_on=spec.blocked_by,
                blocks=spec.blocks,
            )

            task = store.create_task(task_create)
            task_id = task.id
            if await integrator.should_create_task_hook(context):
                hook_spec = await integrator.create_hook_spec(context)
                created_task = TaskCreated(
                    task_id=task.id,
                    parent_id=hook_spec.parent_id,
                    created_at=task.created_at,
                    metadata=hook_spec.metadata,
                )
                await integrator.on_task_created(created_task, context)

            return (
                f"✓ Task created: {task_id}\n\n"
                f"Dependencies: {spec.dependency_summary()}\n\n"
                f"Ready to queue with: village queue --agent {spec.scope}"
            )
        except TaskStoreError as e:
            logger.error(f"Failed to create task: {e}")
            return f"❌ Failed to create task: {e}"

    async def handle_discard(self, args: str) -> str:
        """
        Handle /discard command.

        Works for BOTH:
        - Single task (existing behavior)
        - Breakdown (new: clears breakdown)
        """
        # Case 1: Discard breakdown
        if self.session.current_breakdown:
            task_count = len(self.session.current_breakdown.items)
            self.session.current_breakdown = None
            logger.info(f"Discarded breakdown with {task_count} tasks")
            return f"🗑️ Discarded breakdown ({task_count} subtasks).\n\nUse /create to start a new task."

        # Case 2: Discard single task (existing behavior)
        if not self.session.current_task:
            self.session.query_refinement = None
            return "❌ No current task or breakdown to discard."

        task_title = self.session.current_task.title if self.session.current_task else "task"
        self.session.current_task = None
        self.session.current_iteration = 0
        self.session.refinements = []
        self.session.query_refinement = None

        logger.info(f"Discarded task: {task_title}")
        return f"🗑️ Task '{task_title}' discarded. Use /create to start a new task."

    async def _confirm_breakdown(self) -> str:
        """Create all subtasks from TaskBreakdown."""
        from village.chat.sequential_thinking import validate_dependencies

        breakdown = self.session.current_breakdown
        if not breakdown:
            return "❌ No breakdown to confirm."

        items = breakdown.items

        if not validate_dependencies(breakdown):
            return "❌ Task dependencies are invalid. Use /refine or /edit to fix."

        task_id_map: dict[int, str] = {}
        created_tasks: dict[str, str] = {}
        integrator = self.extensions.get_task_hooks()

        try:
            store = self._get_store()
        except TaskStoreError:
            return "❌ Task store not available. Cannot create tasks."

        for i, item in enumerate(items):
            blocks = [task_id_map[dep] for dep in item.dependencies if dep in task_id_map]

            spec = TaskSpec(
                title=item.title,
                description=item.description,
                scope="feature",
                blocks=blocks,
                blocked_by=[],
                success_criteria=item.success_criteria or ["Task completed"],
                estimate=item.estimated_effort,
                confidence="medium",
                search_hints=item.search_hints,
            )

            context = {
                "task_spec": spec,
                "breakdown_item": item,
                "item_index": i,
                "breakdown": breakdown,
                "session_id": self.session_id,
                "session_context": self.session_context,
                "created_task_ids": task_id_map,
            }

            try:
                task_create = TaskCreate(
                    title=item.title,
                    description=item.description,
                    issue_type="feature",
                    priority=2,
                    depends_on=[task_id_map[dep] for dep in item.dependencies if dep in task_id_map],
                    blocks=blocks,
                )

                if await integrator.should_create_task_hook(context):
                    hook_spec = await integrator.create_hook_spec(context)
                    task = store.create_task(task_create)
                    created_task = TaskCreated(
                        task_id=task.id,
                        parent_id=hook_spec.parent_id,
                        created_at=task.created_at,
                        metadata=hook_spec.metadata,
                    )
                    await integrator.on_task_created(created_task, context)
                    task_id = task.id
                else:
                    task = store.create_task(task_create)
                    task_id = task.id

                task_id_map[i] = task_id
                created_tasks[item.title] = task_id
                logger.info(f"Created subtask {task_id}: {item.title}")
            except TaskStoreError as e:
                logger.error(f"Failed to create task '{item.title}': {e}")
                return self._render_decomposition_error(
                    f"Failed to create task '{item.title}': {e}",
                    task_info=f"Stopped at task {i + 1}/{len(items)}",
                    offer_retry=True,
                )

        self.session.current_breakdown = None

        lines = [f"✓ Created {len(created_tasks)} subtasks:", ""]
        for title, task_id in created_tasks.items():
            lines.append(f"  {task_id}: {title}")

        if breakdown.summary:
            lines.append("")
            lines.append(breakdown.summary)

        return "\n".join(lines)

    async def _refine_breakdown(self, user_input: str) -> str:
        """Refine entire TaskBreakdown based on user feedback."""
        from village.chat.sequential_thinking import validate_dependencies

        breakdown = self.session.current_breakdown
        if not breakdown:
            return "❌ No breakdown to refine."

        # Ask LLM to refine breakdown (Option C: ST analyzes feedback)
        prompt = f"""Current task breakdown:
{self._breakdown_to_text(breakdown)}

User refinement: {user_input}

Analyze this feedback and update ENTIRE breakdown accordingly. Consider:
- Should this be a new subtask?
- Should it modify an existing subtask?
- Does it affect dependencies or ordering?
- Are there conflicts or ambiguities?

Return JSON in same breakdown format:
{{
  "title_original": "...",
  "title_suggested": "...",
  "items": [
    {{
      "title": "...",
      "description": "...",
      "estimated_effort": "...",
      "success_criteria": ["..."],
      "blockers": ["..."],
      "dependencies": [0, 1],
      "tags": ["..."]
    }}
  ],
  "summary": "..."
}}
"""

        import json

        try:
            response = await self._call_llm_with_retry(prompt)

            # Parse refined breakdown
            refined_data = json.loads(response)

            # Parse using _parse_task_breakdown from sequential_thinking
            from village.chat.sequential_thinking import _parse_task_breakdown

            refined_breakdown = _parse_task_breakdown(json.dumps(refined_data))

            # Validate dependencies
            if not validate_dependencies(refined_breakdown):
                return "❌ Refined breakdown has invalid dependencies. Try different refinement."

            # Update session
            self.session.current_breakdown = refined_breakdown

            logger.info(f"Refined breakdown: {refined_breakdown.title_original}")

            return self._render_breakdown(refined_breakdown)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to refine breakdown: {e}")
            return self._render_decomposition_error(
                f"Failed to refine breakdown: {e}",
                task_info=f"Refinement: {user_input}",
                offer_retry=True,
            )

    async def handle_tasks(self, args: str) -> str:
        """Handle /tasks command - list tasks."""
        try:
            store = self._get_store()
            tasks = store.list_tasks(status="open", limit=10)
            if not tasks:
                return "No open tasks found."

            lines = ["\n📋 OPEN TASKS (last 10):\n"]
            for task in tasks:
                lines.append(f"  • {task.id} - {task.title}")

            return "\n".join(lines)
        except TaskStoreError as e:
            logger.error(f"Failed to list tasks: {e}")
            return f"❌ Failed to list tasks: {e}"

    async def handle_task(self, args: str) -> str:
        """Handle /task <id> command - show task details."""
        if not args:
            return "Usage: /task <task-id>"

        task_id = args.strip()
        if not task_id:
            return "Usage: /task <task-id>"

        try:
            store = self._get_store()
            deps = store.get_dependencies(task_id)
            lines = [f"\n📋 TASK: {task_id}\n", "DEPENDENCIES:\n"]
            for dep_task in deps.blocks:
                lines.append(f"  depends on: {dep_task.id} - {dep_task.title}")
            for dep_task in deps.blocked_by:
                lines.append(f"  blocked by: {dep_task.id} - {dep_task.title}")

            if not deps.blocks and not deps.blocked_by:
                return f"Task {task_id} has no dependencies."

            return "\n".join(lines)
        except TaskStoreError as e:
            logger.error(f"Failed to get task dependencies: {e}")
            return f"❌ Failed to get dependencies: {e}"

    async def handle_ready(self, args: str) -> str:
        """Handle /ready command - show ready tasks."""
        try:
            store = self._get_store()
            ready_tasks = store.get_ready_tasks()
            if not ready_tasks:
                return "No ready tasks found."

            lines = ["\n✅ READY TASKS (last 10):\n"]
            for task in ready_tasks[:10]:
                lines.append(f"  • {task.id} - {task.title}")

            return "\n".join(lines)
        except TaskStoreError as e:
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
                confidence=cast(ConfidenceType, cast(str, task_spec_dict.get("confidence", "medium"))),
                search_hints=cast(dict[str, list[str]], task_spec_dict.get("search_hints") or {}),
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
  /confirm                  — Queue current task
  /discard                  — Cancel current task

## Task Query Commands
  /tasks                    — List open tasks
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

Use exact task IDs (e.g., tsk-abc123) for best results.
"""

    def render_task_spec(self, spec: TaskSpec, refinement_count: int = 0) -> str:
        """Render task specification as ASCII box with dependencies."""
        box_width = 46
        lines = []

        lines.append("┌" + "─" * box_width + "┐")
        title_display = f"{spec.title} (Refinement #{refinement_count})" if refinement_count > 0 else spec.title
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
                lines.append("│" + f"   ⬇ BLOCKED BY: {blocked_str} " + " " * (box_width - 42) + "│")
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
        lines.append("│" + f" SUCCESS CRITERIA ({len(spec.success_criteria)}): " + " " * (box_width - 23) + "│")

        for i, criterion in enumerate(spec.success_criteria, 1):
            lines.append("│" + f"   {i}. {criterion[:40]} " + " " * (box_width - 41) + "│")

        lines.append("├" + "─" * box_width + "┤")

        # Confidence indicator
        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        emoji = confidence_emoji[spec.confidence]
        lines.append("│" + f" Confidence: {emoji} {spec.confidence.upper():<30} " + " " * (box_width - 41) + "│")
        lines.append("├" + "─" * box_width + "┤")

        # Commands
        lines.append("│" + " /refine /revise <clarification> - Revise this task      " + " " * (box_width - 55) + "│")
        lines.append("│" + " /undo - Revert to previous version                     " + " " * (box_width - 50) + "│")
        lines.append("│" + " /confirm - Queue this task                              " + " " * (box_width - 50) + "│")
        lines.append("│" + " /discard - Cancel                                       " + " " * (box_width - 43) + "│")
        lines.append("└" + "─" * box_width + "┘")

        return "\n".join(lines)

    def _render_decomposition_error(
        self,
        error_message: str,
        task_info: str | None = None,
        breakdown: str | None = None,
        offer_retry: bool = True,
    ) -> str:
        """Render decomposition error with full context."""
        lines = ["❌ ERROR: Decomposition Failed", ""]
        lines.append(error_message)
        lines.append("")

        if task_info:
            lines.append("Task Information:")
            lines.append(task_info)
            lines.append("")

        if breakdown:
            lines.append("Generated Breakdown (partial or invalid):")
            # Truncate if very long
            breakdown_display = breakdown[:500] if len(breakdown) > 500 else breakdown
            lines.append(breakdown_display)
            if len(breakdown) > 500:
                lines.append(f"[... {len(breakdown) - 500} more characters truncated]")
            lines.append("")

        if offer_retry:
            lines.append("Actions:")
            lines.append("  /retry      Try decomposition again")
            lines.append("  /discard    Cancel and try simpler task")
            lines.append("  /confirm-simple  Create as single task (without breakdown)")

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
        if spec.search_hints:
            hints_parts = []
            for key, values in spec.search_hints.items():
                if values:
                    hints_parts.append(f"{key}: {', '.join(values)}")
            if hints_parts:
                lines.append(f"Search Hints: {'; '.join(hints_parts)}")
        return "\n".join(lines)

    def _get_prompt(self) -> str:
        """Get system prompt for LLM."""
        return """You are a Task Specification Agent for Village.

Your job: Parse conversational input into structured PPC contracts with explicit task IDs for dependencies.

## Dependency Detection Rules

When user mentions dependencies, you MUST:

### Option 1: Use Exact Task ID
If user says "tsk-abc123" or mentions "tsk-abc123", use that exact ID:
{
  "blocks": ["tsk-abc123"],
  "blocked_by": []
}

### Option 2: Use Task Name Pattern
If user says "blocks the dashboard widget", use pattern:
{
  "blocks": ["dashboard-widget"],
  "blocked_by": []
}

**Important**: These patterns will be resolved to actual task IDs by Village after you return the spec.

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

| Pattern | Meaning | Format |
|----------|----------|--------|
| "blocks X" | Current task blocks X | `blocks: [X]` |
| "blocked by Y" | Blocked by Y | `blocked_by: [Y]` |
| "depends on Z" | Depends on Z | `blocked_by: [Z]` |
| "cannot start until A" | Requires A to complete | `blocked_by: [A]` |

## Output Format

### Valid Task Spec
{
  "title": "Task title",
  "description": "Keyword-rich description including: specific module names, file paths "
  "affected, error types, function/class names, and behavioral changes. "
  "Be precise enough that this description could be used as a search query to find related past work.",
  "scope": "fix|feature|config|docs|test|refactor",
  "blocks": ["task-id-1", "task-id-2"],
  "blocked_by": ["task-id-3", "task-id-4"],
  "success_criteria": ["Criterion 1", "Criterion 2", "Criterion 3"],
  "estimate": "X-Y hours|days|weeks",
  "confidence": "high|medium|low",
  "search_hints": {
    "modules": ["affected/file.py", "another/module.py"],
    "concepts": ["key term", "another concept"],
    "patterns": ["error pattern", "behavioral pattern"]
  }
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

## Description Quality Requirements

Write task descriptions that are both human-readable AND search-friendly:
- Always mention specific modules, files, or components affected
- Include error types, function names, or class names where relevant
- Describe the specific behavioral change, not just the general intent
- Use terms that a developer would search for when looking for similar work

Good: "Add retry logic with exponential backoff to queue.py task processing. "
"Handle ConnectionError and TimeoutError from subprocess.run() calls."
Bad: "Handle the retry case properly."

Be concise and focused on task specification only."""
