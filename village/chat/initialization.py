"""Beads initialization for chat mode."""

import logging

from village.config import Config
from village.probes.tools import run_command_output

logger = logging.getLogger(__name__)


def ensure_beads_initialized(config: Config) -> None:
    """
    Ensure Beads is configured with draft status.

    Checks for:
    1. .beads/ directory exists
    2. status.custom config contains "draft"

    If .beads/ doesn't exist: return early (user needs bd init)
    If status configured: no-op
    Otherwise: bd config set status.custom "draft"

    Args:
        config: Village config with git_root path

    Raises:
        SubprocessError: If Beads commands fail
    """
    beads_dir = config.git_root / ".beads"

    if not beads_dir.exists():
        logger.warning(f"Beads not initialized. Run 'bd init' in {config.git_root} first.")
        return

    try:
        output = run_command_output(["bd", "config", "list"])
    except Exception as e:
        logger.warning(f"Failed to check Beads config: {e}")
        return

    if "status.custom" in output:
        existing_status = run_command_output(["bd", "config", "get", "status.custom"])
        statuses = existing_status.split(",")

        if "draft" in statuses:
            logger.info("Beads already configured with 'draft' status")
            return

    logger.info("Configuring Beads with custom 'draft' status")
    run_command_output(["bd", "config", "set", "status.custom", "draft"])
    logger.info("Beads configured: status.custom = 'draft'")


def is_beads_available(config: Config) -> bool:
    """
    Check if Beads is initialized and available.

    Args:
        config: Village config with git_root path

    Returns:
        True if .beads/ directory exists, False otherwise
    """
    beads_dir = config.git_root / ".beads"
    return beads_dir.exists()
