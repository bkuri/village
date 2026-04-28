"""Resume contract generation."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from village.config import AgentConfig, Config, get_config
from village.rules.loader import load_rules

logger = logging.getLogger(__name__)

CONTRACT_VERSION = 1


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
    2. PPC-generated system prompt (hard dependency)

    Args:
        task_id: Task ID (e.g., "bd-a3f8")
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
    content: str = ""
    ppc_profile: Optional[str] = None

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

    # Use PPC if custom contract not used
    if not content:
        from village.ppc import generate_ppc_contract

        rules = load_rules(config.village_dir / "rules.yaml")
        guardrails = rules.guardrails if rules else None

        content = generate_ppc_contract(
            agent,
            agent_config,
            config,
            guardrails=guardrails,
        )
        ppc_mode = agent_config.ppc_mode or "explore"
        ppc_profile = f"ppc:{ppc_mode}"

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
        warnings=[],
        ppc_profile=ppc_profile,
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

    agent_config = config.agents.get(agent, AgentConfig())

    content: str
    ppc_profile: str

    use_ppc = True
    if agent_config.contract:
        contract_path = config.git_root / agent_config.contract
        if contract_path.exists():
            logger.debug(f"Using custom contract: {contract_path}")
            content = contract_path.read_text(encoding="utf-8")
            ppc_profile = f"file:{agent_config.contract}"
            use_ppc = False

    if use_ppc:
        from village.ppc import generate_ppc_contract

        rules = load_rules(config.village_dir / "rules.yaml")
        guardrails = rules.guardrails if rules else None

        spec_vars = {
            "spec_name": spec_path.name,
            "worktree_path": str(worktree_path),
            "git_root": str(config.git_root),
            "window_name": window_name,
            "spec_content": spec_content,
        }

        content = generate_ppc_contract(
            agent,
            agent_config,
            config,
            guardrails=guardrails,
            vars=spec_vars,
        )
        ppc_profile = "spec"

    # Append execution_enforcement guardrail
    ee_path = Path(__file__).parent / "guardrails" / "execution_enforcement.md"
    if ee_path.exists():
        ee_content = ee_path.read_text(encoding="utf-8")
        content += "\n\n" + ee_content

    # Append execution protocol instructions
    from village.execution.protocol import PlanProtocol

    content += "\n" + PlanProtocol.format_contract_section()

    goal_section = _build_goal_context(config, spec_path.name, spec_content[:200])
    if goal_section:
        content = content.rstrip("\n") + "\n\n" + goal_section + "\n"

    return ContractEnvelope(
        version=1,
        format="markdown",
        task_id=task_id,
        agent=agent,
        content=content,
        warnings=[],
        ppc_profile=ppc_profile,
        created_at=created_at,
        task_title=spec_path.name,
        task_description=f"Spec: {spec_path.name}",
    )
