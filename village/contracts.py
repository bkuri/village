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

FALLBACK_CONTRACT_TEMPLATE = """# Task: {task_id} ({agent})

## Goal
Work on task `{task_id}` in isolated workspace.

## Constraints
- Keep changes isolated to this worktree.
- Prefer small commits / coherent diffs.
- If blocked, write a short note to task log.

## Inputs
- Worktree path: `{worktree_path}`
- Git root: `{git_root}`
- Window name: `{window_name}`
- Created: `{created_at}`
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

    Returns:
        Markdown contract string
    """
    return FALLBACK_CONTRACT_TEMPLATE.format(
        task_id=task_id,
        agent=agent,
        worktree_path=str(worktree_path),
        git_root=str(git_root),
        window_name=window_name,
        created_at=created_at.isoformat(),
    )


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
            ppc_mode = (
                agent_config.ppc_mode if agent_config and agent_config.ppc_mode else "explore"
            )
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
        )
        ppc_profile = "fallback"

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
    )
