"""Subprocess execution utilities."""

import logging
import subprocess

logger = logging.getLogger(__name__)


class SubprocessError(Exception):
    """Raised when subprocess fails."""

    pass


def run_command(
    cmd: list[str],
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Run a subprocess command.

    Args:
        cmd: Command and arguments as list (safe, no shell injection)
        capture: Capture stdout/stderr
        check: Raise exception on non-zero exit

    Returns:
        CompletedProcess with results

    Raises:
        SubprocessError: If command fails and check=True
    """
    logger.debug(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )

    if check and result.returncode != 0:
        error_msg = f"Command failed: {' '.join(cmd)}"
        if result.stderr:
            error_msg += f"\n{result.stderr}"
        logger.error(error_msg)
        raise SubprocessError(error_msg)

    logger.debug(f"Exit code: {result.returncode}")
    return result


def run_command_output(cmd: list[str]) -> str:
    """
    Run command and return stdout.

    Args:
        cmd: Command and arguments as list

    Returns:
        stdout as string (stripped)

    Raises:
        SubprocessError: If command fails
    """
    result = run_command(cmd, capture=True, check=True)
    return result.stdout.strip()
