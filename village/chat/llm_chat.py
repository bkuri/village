"""LLM chat session with task specification rendering."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, cast

from village.chat.breakdown import (
    confirm_breakdown,
    offer_decomposition,
    refine_breakdown,
    should_decompose,
)
from village.chat.chat_session import ChatSession
from village.chat.prompts import TASK_SPEC_SYSTEM_PROMPT
from village.chat.renderers import render_task_spec, task_spec_to_text
from village.chat.sequential_thinking import TaskBreakdown
from village.chat.task_spec import TaskSpec
from village.extensibility import ExtensionRegistry
from village.extensibility.context import SessionContext
from village.extensibility.task_hooks import TaskCreated
from village.extensibility.tool_invokers import ToolInvocation, ToolResult
from village.tasks import TaskCreate, TaskStore, TaskStoreError, get_task_store

if TYPE_CHECKING:
    from village.config import Config
    from village.llm.client import LLMClient
    from village.llm.mcp import MCPClient

    _Config = Config
    _LLMClient = LLMClient
    _MCPClient = MCPClient
else:
    _Config = object
    _LLMClient = object
    _MCPClient = object

logger = logging.getLogger(__name__)


SLASH_COMMANDS = {
    "/create": "handle_create",
    "/refine": "handle_refine",
    "/revise": "handle_refine",
    "/undo": "handle_undo",
    "/confirm": "handle_confirm",
    "/discard": "handle_discard",
    "/reset": "handle_discard",
    "/tasks": "handle_tasks",
    "/task": "handle_task",
    "/ready": "handle_ready",
    "/status": "handle_status",
    "/history": "handle_history",
    "/help": "handle_help",
}


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
    mcp_client: _MCPClient | None = None
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
        mcp_client: Optional[_MCPClient] = None,
    ) -> None:
        self.session = ChatSession()
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.config = config
        self.extensions = extensions or ExtensionRegistry()
        self.mcp_client = mcp_client
        self.session_id = str(uuid.uuid4())
        self.session_context = None

    def _get_store(self) -> "TaskStore":
        if self.config is None:
            raise TaskStoreError("Config not available")
        return get_task_store(config=self.config)

    async def set_extensions(self, extensions: ExtensionRegistry) -> None:
        self.extensions = extensions

    async def set_mcp_client(self, mcp_client: _MCPClient) -> None:
        self.mcp_client = mcp_client

    async def _call_llm_with_retry(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_retries: int = 3,
    ) -> str:
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

    def _parse_task_spec_response(self, response: str, defaults: dict | None = None) -> tuple[dict | None, str]:  # type: ignore[type-arg]
        try:
            json_text = response.strip()
            if json_text.startswith("```"):
                json_text = json_text.split("```")[1] if "```" in json_text[3:] else json_text
                if json_text.startswith("json"):
                    json_text = json_text[4:]
            task_spec_dict = json.loads(json_text.strip())
        except json.JSONDecodeError:
            return None, "parse_error"

        required_fields = ["title", "description", "scope"]
        missing_fields = [f for f in required_fields if f not in task_spec_dict]
        if missing_fields:
            return (
                None,
                f"Missing required fields: {', '.join(missing_fields)}\nPlease provide: title, description, scope",
            )

        if defaults:
            for key, value in defaults.items():
                task_spec_dict.setdefault(key, value)
        else:
            task_spec_dict.setdefault("blocks", [])
            task_spec_dict.setdefault("blocked_by", [])
            task_spec_dict.setdefault("success_criteria", [])
            task_spec_dict.setdefault("estimate", "unknown")
            task_spec_dict.setdefault("confidence", "medium")

        return task_spec_dict, ""

    def _get_prompt(self) -> str:
        return TASK_SPEC_SYSTEM_PROMPT

    async def handle_message(self, user_input: str) -> str:
        user_input = user_input.strip()

        processor = self.extensions.get_processor()
        chat_context = self.extensions.get_chat_context()

        if self.session_context is None:
            self.session_context = await chat_context.load_context(self.session_id)

        if user_input.startswith("/"):
            response = await self.handle_slash_command(user_input)
        else:
            user_input = await processor.pre_process(user_input)

            self.session_context = await chat_context.enrich_context(self.session_context)

            refiner = self.extensions.get_thinking_refiner()
            if await refiner.should_refine(user_input):
                self.session.query_refinement = await refiner.refine_query(user_input)
                logger.info(f"Query refined into {len(self.session.query_refinement.refined_steps)} steps")

            if self.session.current_task is None:
                response = await self.handle_create(user_input)
            else:
                response = await self.handle_refine(user_input)

        if self.session_context:
            await chat_context.save_context(self.session_context)

        response = await processor.post_process(response)
        return response

    async def invoke_tool(self, tool_name: str, args: dict[str, object], server_name: str | None = None) -> ToolResult:
        invoker = self.extensions.get_tool_invoker()
        invocation = ToolInvocation(
            tool_name=tool_name,
            args=args,
            context={"session_id": self.session_id, "server_name": server_name},
        )

        if not await invoker.should_invoke(invocation):
            return ToolResult(success=False, result=None, error="Tool invocation skipped by domain filter")

        transformed_args = await invoker.transform_args(invocation)

        try:
            if self.mcp_client is not None and server_name is not None:
                mcp_result = await self.mcp_client.invoke_tool(
                    server_name=server_name,
                    tool_name=tool_name,
                    tool_input=transformed_args,
                )
                processed_result = await invoker.on_success(invocation, mcp_result)
                return ToolResult(success=True, result=processed_result)

            result = {"tool_name": tool_name, "args": transformed_args, "status": "hook_ready"}
            processed_result = await invoker.on_success(invocation, result)
            return ToolResult(success=True, result=processed_result)
        except Exception as e:
            await invoker.on_error(invocation, e)
            return ToolResult(success=False, result=None, error=str(e))

    async def handle_slash_command(self, command: str) -> str:
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
        logger.info(f"Creating task from input: {user_input[:50]}...")

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

        response: str = await self._call_llm_with_retry(
            prompt=prompt,
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        task_spec_dict, error = self._parse_task_spec_response(response)
        if task_spec_dict is None:
            if error == "parse_error":
                return f"Failed to parse LLM response. Got: {response[:200]}"
            return error

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

        self.session.current_task = task_spec
        self.session.current_iteration = 0
        self.session.refinements = []
        self.session.query_refinement = None

        logger.info(f"Task spec created: {task_spec.title}")

        decompose, reasoning = await should_decompose(self.llm_client, self.extensions, task_spec)

        if decompose:
            logger.info(f"Task '{task_spec.title}' identified as complex. Offering decomposition. Reason: {reasoning}")
            breakdown, rendered = await offer_decomposition(
                self.llm_client, self.config, task_spec, user_input, self.extensions
            )
            if breakdown is not None:
                self.session.current_breakdown = breakdown
                self.session.current_task = task_spec
                logger.info(f"Generated breakdown with {len(breakdown.items)} subtasks")
            return rendered

        return self.render_task_spec(task_spec)

    async def handle_refine(self, user_input: str) -> str:
        if self.session.current_breakdown:
            return await refine_breakdown(self.llm_client, self.extensions, self.session, user_input)

        if not self.session.current_task:
            return "❌ No current task or breakdown to refine. Use /create to start a new task."

        logger.info(f"Refining task with input: {user_input[:50]}...")

        current_spec = self.session.get_current_spec()
        if not current_spec:
            return "❌ No current task specification."

        response = await self._call_llm_with_retry(
            prompt=(
                f"Current task:\n{task_spec_to_text(current_spec)}\n\n"
                f"User refinement: {user_input}\n\n"
                "Update task specification based on this feedback. "
                "Preserve as much as possible, only change what refinement explicitly addresses. "
                "Extract any new dependencies. Return JSON only."
            ),
            system_prompt=self.system_prompt or self._get_prompt(),
        )

        refined_dict, _ = self._parse_task_spec_response(
            response,
            defaults={
                "blocks": current_spec.blocks,
                "blocked_by": current_spec.blocked_by,
                "success_criteria": current_spec.success_criteria,
                "estimate": current_spec.estimate,
                "confidence": current_spec.confidence,
            },
        )
        if refined_dict is None:
            return f"❌ Failed to parse refinement. Got: {response[:100]}"

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

        self.session.add_refinement(refined_spec, user_input)

        summary = refined_dict.get("refinement_summary", "Updated based on feedback")
        logger.info(f"Task refined (iteration {self.session.current_iteration}): {refined_spec.title} - {summary}")

        return self.render_task_spec(refined_spec, self.session.current_iteration)

    async def handle_undo(self, args: str) -> str:
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
        if self.session.current_breakdown:
            try:
                store = self._get_store()
            except TaskStoreError:
                return "❌ Task store not available. Cannot create tasks."
            return await confirm_breakdown(self.session, store, self.extensions, self.session_id, self.session_context)

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
        if self.session.current_breakdown:
            task_count = len(self.session.current_breakdown.items)
            self.session.current_breakdown = None
            logger.info(f"Discarded breakdown with {task_count} tasks")
            return f"🗑️ Discarded breakdown ({task_count} subtasks).\n\nUse /create to start a new task."

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

    async def handle_tasks(self, args: str) -> str:
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
        if not self.session.refinements:
            return "No refinement history yet."

        lines = ["\n📝 REFINEMENT HISTORY:\n"]
        for ref in self.session.refinements:
            task_spec_dict = cast(dict[str, object], ref["task_spec"])
            task_spec = TaskSpec.from_dict(task_spec_dict)
            lines.append(f"  #{ref['iteration']}: {task_spec.title}")
            lines.append(f"     User: {ref['user_input']}")
            lines.append(f"     {task_spec.scope} - {task_spec.estimate}")

        return "\n".join(lines)

    def handle_help(self, args: str) -> str:
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
        return render_task_spec(spec, refinement_count)

    def _render_breakdown(self, breakdown: TaskBreakdown) -> str:
        from village.chat.renderers import render_breakdown

        return render_breakdown(breakdown)

    def _breakdown_to_text(self, breakdown: TaskBreakdown) -> str:
        from village.chat.renderers import breakdown_to_text

        return breakdown_to_text(breakdown)

    def _render_decomposition_error(
        self,
        error_message: str,
        task_info: str | None = None,
        breakdown: str | None = None,
        offer_retry: bool = True,
    ) -> str:
        from village.chat.renderers import render_decomposition_error

        return render_decomposition_error(error_message, task_info, breakdown, offer_retry)

    def _task_spec_to_text(self, spec: TaskSpec) -> str:
        return task_spec_to_text(spec)
