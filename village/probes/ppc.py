"""PPC detection probe."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from village.config import Config
from village.probes.tools import SubprocessError, run_command_output

logger = logging.getLogger(__name__)


@dataclass
class PPCStatus:
    """PPC availability status."""

    available: bool
    version: Optional[str]
    prompts_dir: Optional[Path]


def detect_ppc(config: Config) -> PPCStatus:
    """
    Detect PPC availability.

    Checks:
    1. ppc binary in PATH (run `ppc --version`)
    2. prompts/ directory in git_root (optional for v1)

    Pure function - no side effects.

    Args:
        config: Config object

    Returns:
        PPCStatus with availability information
    """
    try:
        result = run_command_output(["ppc", "--version"])
        version = result.strip()
        prompts_dir = config.git_root / "prompts" if config.git_root else None

        return PPCStatus(
            available=True,
            version=version,
            prompts_dir=prompts_dir if prompts_dir and prompts_dir.exists() else None,
        )
    except (SubprocessError, FileNotFoundError):
        return PPCStatus(available=False, version=None, prompts_dir=None)
