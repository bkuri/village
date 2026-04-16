"""Core conversation orchestration."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from village.chat.context import (
    ContextFile,
    ContextUpdate,
    apply_context_update,
    get_context_dir,
    get_current_context,
)
from village.chat.prompts import ChatMode, generate_initial_prompt, generate_mode_prompt
from village.chat.schema import validate_schema
from village.chat.state import (
    SessionSnapshot,
    take_session_snapshot,
)
from village.chat.subcommands import execute_command, parse_command
from village.chat.task_commands import handle_task_subcommand
from village.llm import get_llm_client
from village.tasks import TaskStoreError, get_task_store

if TYPE_CHECKING:
    from village.config import Config

    _Config = Config
else:
    from village.config import Config as _Config  # type: ignore[misc]

logger = logging.getLogger(__name__)


def get_task_workflow_context(config: _Config) -> str:
    """
    Get workflow context from the task store.

    This provides AI-optimized workflow context (~50 tokens) that
    helps agents remember workflow details across context compaction.

    Args:
        config: Village config

    Returns:
        Workflow context string (empty if store not available)
    """
    try:
        store = get_task_store(config=config)
        return store.get_prime_context()
    except TaskStoreError as e:
        logger.warning(f"Failed to get workflow context: {e}")
        return ""


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

    task_workflow = get_task_workflow_context(config)
    if task_workflow:
        prompt += f"\n\n## Task Workflow Context\n\n{task_workflow}\n"

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


async def process_user_input(state: ConversationState, user_input: str, config: _Config) -> ConversationState:
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
        state = handle_task_subcommand(state, parsed.command, parsed.args, config)
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
            state.context_files[filename] = ContextFile(name=filename, path=written_files[filename], content=content)
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


def _call_llm(messages: list[ConversationMessage], config: _Config, mode: str = "knowledge-share") -> str:
    """
    Call LLM via provider-agnostic client.

    Args:
        messages: Conversation messages
        config: Village config
        mode: Chat mode (knowledge-share or task-create)

    Returns:
        LLM response string
    """
    conversation = "\n\n".join([f"{m.role}: {m.content}" for m in messages[-10:]])

    try:
        llm_client = get_llm_client(config)
        response = llm_client.call(
            conversation,
            timeout=config.llm.timeout,
            max_tokens=config.llm.max_tokens,
        )

        return response
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return f"Error: Failed to call LLM ({e})"


def should_exit(user_input: str) -> bool:
    """Check if user wants to exit."""
    return user_input.strip().lower() in {"/exit", "/quit", "/bye"}
