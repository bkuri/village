"""Prompt generation via PPC (hard dependency)."""

import enum
import logging
from typing import TYPE_CHECKING

from village.chat.errors import PromptGenerationError
from village.config import Config
from village.probes.tools import SubprocessError, run_command_output_cwd

if TYPE_CHECKING:
    _Config = Config
else:
    _Config = object

logger = logging.getLogger(__name__)


class ChatMode(enum.Enum):
    """Chat mode for prompt generation."""

    KNOWLEDGE_SHARE = "knowledge-share"
    TASK_CREATE = "task-create"


def generate_mode_prompt(config: _Config, mode: ChatMode) -> tuple[str, str]:
    """Generate prompt for specific chat mode using PPC.

    Returns:
        (prompt, "ppc")
    """
    prompt = _compile_ppc_prompt(config, mode)
    return prompt, "ppc"


def generate_initial_prompt(config: Config) -> tuple[str, str]:
    """Generate initial prompt using default mode.

    Returns:
        (prompt, "ppc")
    """
    return generate_mode_prompt(config, ChatMode.KNOWLEDGE_SHARE)


def _compile_ppc_prompt(config: _Config, mode: ChatMode) -> str:
    """Compile PPC prompt for village-chat or village-create.

    Raises:
        PromptGenerationError: If PPC compilation fails
    """
    profiles_dir = config.git_root / "profiles"

    profile_name = f"village-{mode.value}"
    profile_path = profiles_dir / f"{profile_name}.yml"

    if not profile_path.exists():
        raise PromptGenerationError(
            f"PPC profile not found: {profile_path}. Create a profile at that path or adjust chat mode."
        )

    cmd = ["ppc", "explore", "--profile", profile_name]
    # Use village-specific prompts for chat profiles
    village_prompts = config.village_dir.parent / "village" / "prompts"
    if village_prompts.is_dir():
        cmd.extend(["-prompts", str(village_prompts)])

    try:
        return run_command_output_cwd(cmd, cwd=config.git_root)
    except SubprocessError as e:
        raise PromptGenerationError(f"PPC compilation failed: {e}") from e


TASK_SPEC_SYSTEM_PROMPT = """You are a Task Specification Agent for Village.

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
