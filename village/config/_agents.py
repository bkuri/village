from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for a single agent type."""

    opencode_args: str = ""
    ppc_mode: Optional[str] = None
    ppc_traits: list[str] = field(default_factory=list)
    ppc_format: str = "markdown"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    type: str = "opencode"
    pi_args: str = ""
    acp_command: Optional[str] = None
    acp_capabilities: list[str] = field(default_factory=list)


def _parse_ppc_traits(value: str) -> list[str]:
    if not value:
        return []
    return [t.strip().lower() for t in value.split(",") if t.strip()]


def _validate_acp_agent(agent_name: str, agent_config: AgentConfig) -> list[str]:
    errors = []

    if agent_config.type == "acp":
        if not agent_config.acp_command:
            errors.append(f"ACP agent '{agent_name}' missing required field 'acp_command'")

        if agent_config.acp_command:
            cmd_parts = agent_config.acp_command.split()
            if cmd_parts:
                executable = cmd_parts[0]
                if "/" not in executable:
                    pass
                else:
                    if not Path(executable).exists():
                        errors.append(f"ACP agent '{agent_name}' command executable not found: {executable}")

    return errors
