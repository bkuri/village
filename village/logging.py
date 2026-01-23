"""Logging configuration."""

import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for village.

    Logs go to stderr, not mixed with CLI output (--json, --short).

    Args:
        verbose: If True, log at DEBUG level; otherwise WARNING.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(name)s: %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (e.g., "village.probes.tmux")

    Returns:
        Logger instance
    """
    return logging.getLogger(f"village.{name}")
