"""Resume contract generation."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from village.config import AgentConfig, Config, get_config

logger = logging.getLogger(__name__)

CONTRACT_VERSION = 1

SPEC_CONTRACT_TEMPLATE = """# Spec: {spec_name}

You are running inside a spec-driven autonomous build loop.

## Your Mission

1. Read the spec below carefully, including any "Inspect Notes" sections.
2. Look at any existing notes from previous attempts (if available).
3. Implement the spec FULLY:
   - Write all required code
   - Write all required tests
   - Run linting/formatting
   - Run tests
   - Fix any issues
4. When ALL acceptance criteria are verified and tests pass:
   - Add "Status: COMPLETE" to the top of the spec file
   - Commit changes with a descriptive message
5. Output `<promise>DONE</promise>` ONLY when everything is done.

## Critical Rules

- Do NOT ask for permission. Be fully autonomous.
- Do NOT skip any acceptance criteria. Verify EACH one.
- Treat "Inspect Notes" as hard constraints — same priority as acceptance criteria.
- Do NOT output `<promise>DONE</promise>` unless ALL criteria pass.
- If validation commands fail, fix them and try again.
- This spec is independent — implement it completely in this iteration.

## Workspace

- Worktree path: `{worktree_path}`
- Git root: `{git_root}`
- Window name: `{window_name}`
- Created: `{created_at}`

## Trace Recording
Record audit events to: `{traces_dir}/{task_id}.jsonl`
Events: task_checkout, tool_call, decision, file_modified, task_complete
Format: one JSON object per line with keys: timestamp, event_type, task_id, agent, data, sequence

---

## Spec: {spec_name}

{spec_content}
"""

FALLBACK_CONTRACT_TEMPLATE = """# Task: {task_id} ({agent})

## Goal
Work on task `{task_id}` in isolated workspace.

## Task
- Title: {task_title}
- Description: {task_description}

## Constraints
- Keep changes isolated to this worktree.
- Prefer small commits / coherent diffs.
- If blocked, write a short note to task log.

## Inputs
- Worktree path: `{worktree_path}`
- Git root: `{git_root}`
- Window name: `{window_name}`
- Created: `{created_at}`

## Trace Recording
Record audit events to: `{traces_dir}/{task_id}.jsonl`
Events: task_checkout, tool_call, decision, file_modified, task_complete
Format: one JSON object per line with keys: timestamp, event_type, task_id, agent, data, sequence
"""


@dataclass
class ContractEnvelope:
    """Internal contract representation with JSON envelope."""

    version: int = 1
    format: str = "markdown"
    task_id: str = ""
    agent: str = ""
    content: str = ""
    warnings: list[str] = field(default_factory=list)
    ppc_profile: Optional[str] = None
    ppc_version: Optional[str] = None
    created_at: str = ""
    task_title: str = ""
    task_description: str = ""

    def to_json(self) -> str:
        """Serialize to JSON envelope."""
        return json.dumps(
            {
                "version": self.version,
                "format": self.format,
                "task_id": self.task_id,
                "agent": self.agent,
                "content": self.content,
                "warnings": self.warnings,
                "ppc_profile": self.ppc_profile,
                "ppc_version": self.ppc_version,
                "created_at": self.created_at,
                "task_title": self.task_title,
                "task_description": self.task_description,
            },
            sort_keys=True,
        )


def generate_fallback_contract(
    task_id: str,
    agent: str,
    worktree_path: Path,
    git_root: Path,
    window_name: str,
    created_at: datetime,
    task_title: str = "",
    task_description: str = "",
) -> str:
    """
    Generate minimal fallback contract (Markdown).

    Pure function - no side effects.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        agent: Agent name (e.g., "build")
        worktree_path: Path to worktree directory
        git_root: Git repository root
        window_name: Tmux window name
        created_at: Contract creation timestamp
        task_title: Task title from Beads
        task_description: Task description from Beads

    Returns:
        Markdown contract string
    """
    config = get_config()

    return FALLBACK_CONTRACT_TEMPLATE.format(
        task_id=task_id,
        agent=agent,
        worktree_path=str(worktree_path),
        git_root=str(git_root),
        window_name=window_name,
        created_at=created_at.isoformat(),
        task_title=task_title,
        task_description=task_description,
        traces_dir=str(config.traces_dir),
    )


def _build_goal_context(config: Config, task_title: str, task_description: str) -> str:
    """Find the most relevant active goal and build context section."""
    try:
        from village.goals import get_active_goals, get_goal_chain, parse_goals

        goals_path = config.git_root / "GOALS.md"
        all_goals = parse_goals(goals_path)
        if not all_goals:
            return ""

        active = get_active_goals(all_goals)
        if not active:
            return ""

        search_text = (task_title + " " + task_description).lower()
        best_goal = None
        best_score = 0.0

        for goal in active:
            score = 0.0
            goal_text = (goal.title + " " + goal.description).lower()
            for word in search_text.split():
                if len(word) > 2 and word in goal_text:
                    score += 1.0
            if score > best_score:
                best_score = score
                best_goal = goal

        if best_goal is None:
            best_goal = active[0]

        chain = get_goal_chain(all_goals, best_goal.id)
        chain_str = " → ".join(f"{g.id}: {g.title}" for g in chain)

        lines = ["## Current Objective", ""]
        lines.append(f"Goal chain: {chain_str}")
        if best_goal.description:
            lines.append(f"Context: {best_goal.description}")
        if best_goal.objectives:
            lines.append("Key objectives:")
            for obj in best_goal.objectives[:5]:
                lines.append(f"- {obj}")
        lines.append("")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"Could not build goal context: {e}")
        return ""


def generate_contract(
    task_id: str,
    agent: str,
    worktree_path: Path,
    window_name: str,
    config: Optional[Config] = None,
) -> ContractEnvelope:
    """
    Generate contract envelope (pure function).

    Priority:
    1. Custom contract file from agent config (if exists)
    2. PPC-generated system prompt (if available)
    3. Fallback Markdown template (always available)

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        agent: Agent name (e.g., "build", "frontend")
        worktree_path: Path to worktree directory
        window_name: Tmux window name
        config: Optional config (uses default if not provided)

    Returns:
        ContractEnvelope with content and metadata
    """
    if config is None:
        config = get_config()

    created_at = datetime.now().isoformat()
    warnings: list[str] = []
    content: str = ""
    ppc_profile: Optional[str] = None
    ppc_version: Optional[str] = None

    task_title = ""
    task_description = ""

    from village.tasks import TaskNotFoundError, get_task_store

    try:
        store = get_task_store(config=config)
        task = store.get_task(task_id)
        if task is not None:
            task_title = task.title
            task_description = task.description
    except TaskNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"Could not fetch task details from task store: {e}")

    # Resolve agent config
    agent_config = config.agents.get(agent, AgentConfig())

    # Try custom contract file first (explicit > implicit)
    if agent_config.contract:
        contract_path = config.git_root / agent_config.contract
        if contract_path.exists():
            logger.debug(f"Using custom contract: {contract_path}")
            content = contract_path.read_text(encoding="utf-8")
            ppc_profile = f"file:{agent_config.contract}"
        else:
            warnings.append(f"contract_file_not_found: {contract_path}")

    # Try PPC if custom contract not used
    if not content:
        from village.ppc import generate_ppc_contract

        ppc_prompt, ppc_error = generate_ppc_contract(agent, agent_config, config)
        if ppc_prompt:
            content = ppc_prompt
            from village.probes.ppc import detect_ppc

            ppc_status = detect_ppc(config)
            if ppc_status.version:
                ppc_version = ppc_status.version
            ppc_mode = agent_config.ppc_mode if agent_config and agent_config.ppc_mode else "explore"
            ppc_profile = f"ppc:{ppc_mode}"
        elif ppc_error:
            warnings.append(ppc_error)

    # Fallback template (always available)
    if not content:
        content = generate_fallback_contract(
            task_id,
            agent,
            worktree_path,
            config.git_root,
            window_name,
            datetime.fromisoformat(created_at),
            task_title=task_title,
            task_description=task_description,
        )
        ppc_profile = "fallback"

    if ppc_profile != "fallback":
        trace_section = (
            f"\n## Trace Recording\n"
            f"Record audit events to: `{config.traces_dir}/{task_id}.jsonl`\n"
            f"Events: task_checkout, tool_call, decision, file_modified, task_complete\n"
            f"Format: one JSON object per line with keys: timestamp, event_type, task_id, agent, data, sequence\n"
        )
        content = content.rstrip("\n") + trace_section + "\n"

    goal_section = _build_goal_context(config, task_title, task_description)
    if goal_section:
        content = content.rstrip("\n") + "\n\n" + goal_section + "\n"

    return ContractEnvelope(
        version=1,
        format="markdown",
        task_id=task_id,
        agent=agent,
        content=content,
        warnings=warnings,
        ppc_profile=ppc_profile,
        ppc_version=ppc_version,
        created_at=created_at,
        task_title=task_title,
        task_description=task_description,
    )


def generate_spec_contract(
    spec_path: Path,
    spec_content: str,
    agent: str,
    worktree_path: Path,
    window_name: str,
    model: str | None = None,
    config: Config | None = None,
) -> ContractEnvelope:
    """Generate a contract for spec-driven autonomous building.

    Args:
        spec_path: Path to the spec file
        spec_content: Raw content of the spec file
        agent: Agent name
        worktree_path: Path to worktree directory
        window_name: Tmux window name
        model: Optional model override
        config: Optional config

    Returns:
        ContractEnvelope with spec content as the contract body
    """
    if config is None:
        config = get_config()

    created_at = datetime.now().isoformat()
    task_id = spec_path.stem
    warnings: list[str] = []

    agent_config = config.agents.get(agent, AgentConfig())

    if agent_config.contract:
        contract_path = config.git_root / agent_config.contract
        if contract_path.exists():
            logger.debug(f"Using custom contract: {contract_path}")
            content = contract_path.read_text(encoding="utf-8")
            ppc_profile = f"file:{agent_config.contract}"
        else:
            warnings.append(f"contract_file_not_found: {contract_path}")
            content = SPEC_CONTRACT_TEMPLATE.format(
                spec_name=spec_path.name,
                task_id=task_id,
                agent=agent,
                worktree_path=str(worktree_path),
                git_root=str(config.git_root),
                window_name=window_name,
                created_at=created_at,
                traces_dir=str(config.traces_dir),
                spec_content=spec_content,
            )
            ppc_profile = "spec"
    else:
        content = SPEC_CONTRACT_TEMPLATE.format(
            spec_name=spec_path.name,
            task_id=task_id,
            agent=agent,
            worktree_path=str(worktree_path),
            git_root=str(config.git_root),
            window_name=window_name,
            created_at=created_at,
            traces_dir=str(config.traces_dir),
            spec_content=spec_content,
        )
        ppc_profile = "spec"

    goal_section = _build_goal_context(config, spec_path.name, spec_content[:200])
    if goal_section:
        content = content.rstrip("\n") + "\n\n" + goal_section + "\n"

    return ContractEnvelope(
        version=1,
        format="markdown",
        task_id=task_id,
        agent=agent,
        content=content,
        warnings=warnings,
        ppc_profile=ppc_profile,
        created_at=created_at,
        task_title=spec_path.name,
        task_description=f"Spec: {spec_path.name}",
    )
