"""PPC contract generation — hard dependency.

PPC is a required Go binary. This module provides:
- Early availability check (fail-fast)
- Contract generation via PPC CLI
"""

import logging
import shutil
from pathlib import Path

import click

from village.config import AgentConfig, Config
from village.probes.tools import SubprocessError, run_command_output_cwd

logger = logging.getLogger(__name__)

PPC_INSTALL_URL = "https://github.com/bkuri/ppc"

# Resolve PPC prompts directory relative to the village package
_PPC_PROMPTS: str | None = None
_prompts_path = Path(__file__).resolve().parent.parent / "prompts"
if _prompts_path.is_dir():
    _PPC_PROMPTS = str(_prompts_path)


def require_ppc() -> None:
    """Check that the PPC binary is available on PATH.

    Raises:
        click.ClickException: If PPC is not found.
    """
    if not shutil.which("ppc"):
        raise click.ClickException(f"PPC is required but not found on PATH. Install: {PPC_INSTALL_URL}")


def generate_ppc_contract(
    agent: str,
    agent_config: AgentConfig,
    config: Config,
    guardrails: list[str] | None = None,
    vars: dict[str, str] | None = None,
) -> str:
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
    if _PPC_PROMPTS is not None:
        cmd.extend(["-prompts", _PPC_PROMPTS])

    try:
        return run_command_output_cwd(cmd, cwd=config.git_root)
    except SubprocessError as e:
        raise click.ClickException(f"PPC execution failed: {e}. Install: {PPC_INSTALL_URL}") from e
