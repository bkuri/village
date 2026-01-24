"""PPC contract generation."""

import logging
from typing import Optional

from village.config import AgentConfig, Config
from village.probes.ppc import detect_ppc
from village.probes.tools import SubprocessError, run_command_output_cwd

logger = logging.getLogger(__name__)


def generate_ppc_contract(
    agent: str,
    agent_config: AgentConfig,
    config: Config,
) -> tuple[Optional[str], Optional[str]]:
    """
    Generate system prompt using PPC.

    Pure function - no side effects.

    Args:
        agent: Agent name
        agent_config: Agent configuration (with PPC fields)
        config: Village config

    Returns:
        Tuple of (system_prompt, warning) - either (prompt, None) or (None, error_message)
    """
    ppc_status = detect_ppc(config)
    if not ppc_status.available:
        return None, "ppc_not_available"

    mode = agent_config.ppc_mode or "explore"
    traits = agent_config.ppc_traits
    contract_type = agent_config.ppc_format or "markdown"

    cmd = ["ppc", mode]
    for trait in traits:
        cmd.append(f"--{trait}")
    cmd.extend(["--contract", contract_type])

    try:
        result = run_command_output_cwd(cmd, cwd=config.git_root)
        return result, None
    except SubprocessError as e:
        return None, f"ppc_execution_failed: {e}"
