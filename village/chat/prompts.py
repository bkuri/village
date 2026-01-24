"""Prompt generation (PPC + Fabric → Fabric → Embedded)."""

import enum
import logging
from typing import TYPE_CHECKING

from village.chat.errors import PromptGenerationError
from village.config import Config
from village.probes.tools import SubprocessError, run_command_output, run_command_output_cwd

if TYPE_CHECKING:
    _Config = Config
else:
    _Config = object

logger = logging.getLogger(__name__)


class ChatMode(enum.Enum):
    """Chat mode for prompt generation."""

    KNOWLEDGE_SHARE = "knowledge-share"
    TASK_CREATE = "task-create"


DEFAULT_PPC_PROMPT = """---
id: base
desc: Village Chat facilitator for project knowledge sharing.
priority: 0
tags: []
requires: []
---

## Agent Identity

You are "Village Chat" facilitator. Your job is to help a human clarify and
record shared project understanding. You do NOT execute work. You do NOT
create tasks. You produce durable context files.

## Hard Rules

- Never run tools automatically. Only react to explicit user `/commands`.
- Never propose or perform side-effectful actions (queue/resume/up/down).
- Prefer questions over assumptions when missing context is material.
- Keep outputs compact and structured; avoid long essays.
- Always respond with JSON format for context updates.

## Output Format

You must respond with JSON in this exact format:

```json
{
  "writes": {
    "project.md": "# Project\\\\n\\\\nSummary (2-5 lines)...",
    "goals.md": "# Goals\\\\n\\\\n## Goals\\\\n- ...",
    "constraints.md": "# Constraints\\\\n\\\\n## Technical\\\\n- ...",
    "assumptions.md": "# Assumptions\\\\n\\\\n## Assumptions\\\\n- ...",
    "decisions.md": "# Decisions\\\\n\\\\n## Decisions\\\\n- ...",
    "open-questions.md": "# Open Questions\\\\n\\\\n## Questions\\\\n- ..."
  },
  "notes": ["Optional metadata from LLM"],
  "open_questions": ["Optional extracted questions"]
}
```

## Subcommands

If user types a `/command`, treat its stdout/stderr as ground truth.
Incorporate it into drafts under "Evidence". Do not reinterpret it.

Supported commands (v1):
- /tasks - list Beads tasks
- /task <id> - show task details
- /ready - show ready tasks (Beads)
- /status - show Village status summary
- /help [topic] - show help
- /queue - alias for /ready
- /lock - show active locks
- /cleanup - show cleanup plan (read-only)

## Interaction Loop

1. Ask 1-3 high-leverage questions (or 0 if user message is already clear).
2. If user requests grounding, suggest a single relevant `/command`.
3. After new facts arrive (from user or subcommand output), update drafts.

## Refusal / Safety

If user requests execution (e.g., run queue/resume) respond:
- "That's execution; outside chat mode."
- Suggest switching back to `village ready` / `village queue` in normal CLI use.

## Tone

Be crisp, collaborative, and practical.
"""


def detect_prompt_backend() -> tuple[str, str | None]:
    """
    Detect available prompt backend.

    Returns:
        (backend_name, warning/error)

    Priority:
        1. "ppc_fabric" - both PPC and Fabric available
        2. "fabric" - only Fabric available
        3. "embedded" - fallback
    """
    ppc_available = False
    fabric_available = False

    try:
        run_command_output(["ppc", "--version"])
        ppc_available = True
        logger.debug("PPC detected")
    except (SubprocessError, FileNotFoundError):
        logger.debug("PPC not available")

    try:
        run_command_output(["fabric-ai", "--version"])
        fabric_available = True
        logger.debug("Fabric detected")
    except (SubprocessError, FileNotFoundError):
        logger.debug("Fabric not available")

    if ppc_available and fabric_available:
        return "ppc_fabric", None
    elif fabric_available:
        return "fabric", None
    else:
        return "embedded", "No backend available, using embedded fallback"


def generate_mode_prompt(config: _Config, mode: ChatMode) -> tuple[str, str]:
    """
    Generate prompt for specific chat mode using detected backend.

    Args:
        config: Village config
        mode: Chat mode (KNOWLEDGE_SHARE or TASK_CREATE)

    Returns:
        (prompt, backend_name)

    Raises:
        PromptGenerationError: If prompt generation fails
    """
    backend, warning = detect_prompt_backend()

    if backend == "ppc_fabric":
        prompt = _compile_ppc_prompt(config, mode)
        return prompt, backend
    elif backend == "fabric":
        prompt = _load_fabric_context(config, mode)
        return prompt, backend
    else:
        prompt = _get_embedded_fallback(mode)
        return prompt, backend


def generate_initial_prompt(config: Config) -> tuple[str, str]:
    """
    Generate initial prompt using default mode.

    Args:
        config: Village config

    Returns:
        (prompt, backend_name)

    Raises:
        PromptGenerationError: If prompt generation fails
    """
    return generate_mode_prompt(config, ChatMode.KNOWLEDGE_SHARE)


def _compile_ppc_prompt(config: _Config, mode: ChatMode) -> str:
    """
    Compile PPC prompt for village-chat or village-create.

    Args:
        config: Village config
        mode: Chat mode (KNOWLEDGE_SHARE or TASK_CREATE)

    Returns:
        Compiled prompt from PPC

    Raises:
        PromptGenerationError: If PPC compilation fails
    """
    profiles_dir = config.git_root / "profiles"

    # Map mode to profile name
    profile_name = f"village-{mode.value}"
    profile_path = profiles_dir / f"{profile_name}.yml"

    # Check if profile exists
    if not profile_path.exists():
        logger.warning(f"PPC profile not found: {profile_path}")
        # Fall back to embedded
        return _get_embedded_fallback(mode)

    cmd = ["ppc", "explore", "--profile", profile_name]

    try:
        result = run_command_output_cwd(cmd, cwd=config.git_root)
        return result
    except SubprocessError as e:
        raise PromptGenerationError(f"PPC compilation failed: {e}")


def _load_fabric_context(config: _Config, mode: ChatMode) -> str:
    """
    Load Fabric pattern file for village-chat or task-create.

    Args:
        config: Village config
        mode: Chat mode (KNOWLEDGE_SHARE or TASK_CREATE)

    Returns:
        Context prompt text

    Raises:
        PromptGenerationError: If pattern file not found
    """
    if mode == ChatMode.TASK_CREATE:
        pattern_path = config.git_root / "docs/chat/FABRIC_PATTERN_task-create.md"
    else:
        pattern_path = config.git_root / "docs/chat/FABRIC_PROMPT_village-chat.md"

    if not pattern_path.exists():
        raise PromptGenerationError(f"Fabric pattern not found: {pattern_path}")

    return pattern_path.read_text(encoding="utf-8")


def _get_embedded_fallback(mode: ChatMode) -> str:
    """
    Get embedded fallback prompt for specific mode.

    Args:
        mode: Chat mode (KNOWLEDGE_SHARE or TASK_CREATE)

    Returns:
        Hardcoded prompt for the mode
    """
    if mode == ChatMode.TASK_CREATE:
        return """---
id: base
title: Village Task Creation (embedded)
description: Embedded prompt for task creation (no PPC/Fabric)
requires: []
---

You are Village Task Creation assistant. Your job is to conduct a
structured interview to define a task for the Beads task system.

Follow this sequence of phases:

1. Intent: What is the goal? What type (feature/fix/investigation/refactoring)?
2. Context: Which goals relate? Any blockers? Validate constraints?
3. Success: How done? Estimate (hours/days/weeks/unknown)?
4. Validation: Check goals/constraints/decisions, surface conflicts.
5. Manifest: Output JSON task manifest.

Output must be valid JSON with this structure:
{
  "id": "draft-abc123",
  "title": "...",
  "description": "...",
  "scope": "feature|fix|investigation|refactoring",
  "relates_to_goals": [...],
  "success_criteria": [...],
  "blockers": [...],
  "estimate": "hours|days|weeks|unknown",
  "tags": [...],
  "notes": [...],
  "llm_notes": [...]
}

INPUT:
"""
    else:
        return DEFAULT_PPC_PROMPT
