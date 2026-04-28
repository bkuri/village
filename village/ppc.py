"""PPC contract generation."""

import logging

import click

from village.config import AgentConfig, Config
from village.probes.tools import SubprocessError, run_command_output_cwd

logger = logging.getLogger(__name__)


def generate_ppc_contract(
    agent: str,
    agent_config: AgentConfig,
    config: Config,
    guardrails: list[str] | None = None,
    vars: dict[str, str] | None = None,
) -> str:
    """
    Generate system prompt using PPC.

    Pure function - no side effects.

    Args:
        agent: Agent name
        agent_config: Agent configuration (with PPC fields)
        config: Village config
        guardrails: Optional list of guardrail module names to pass to PPC
        vars: Optional dict of variables to pass to PPC via --var flags

    Returns:
        System prompt string

    Raises:
        click.ClickException: If PPC execution fails
    """
    mode = agent_config.ppc_mode or "explore"
    traits = agent_config.ppc_traits
    contract_type = agent_config.ppc_format or "markdown"

    cmd = ["ppc", mode]
    for trait in traits:
        cmd.append(f"--{trait}")
    if guardrails:
        cmd.extend(["--guardrails", ",".join(guardrails)])
    cmd.extend(["--contract", contract_type])
    if vars:
        for key, value in vars.items():
            cmd.extend(["--var", f"{key}={value}"])
        cmd.extend(["--policies", "spec_context"])

    try:
        return run_command_output_cwd(cmd, cwd=config.git_root)
    except SubprocessError as e:
        raise click.ClickException(f"PPC is required but failed: {e}. Install PPC: https://github.com/bkuri/ppc") from e
