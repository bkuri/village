"""Resource limits — OS-level resource enforcement for command execution.

Prevents fork bombs, memory exhaustion, and runaway CPU usage by applying
:func:`resource.setrlimit` before executing agent commands.  The
:class:`ResourceGuard` wraps :class:`subprocess.run` with configurable limits
and applies them in the child process via ``preexec_fn``.

Platform notes:

- ``resource.setrlimit`` is **Linux-only**. On other platforms the guard
  gracefully degrades to using ``subprocess.run``'s ``timeout`` parameter
  (wall-clock only).
- Address space (:data:`resource.RLIMIT_AS`) limits prevent memory
  exhaustion attacks.
- :data:`resource.RLIMIT_NPROC` prevents fork bombs.
"""

from __future__ import annotations

import logging
import resource
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits for command execution.

    All limits are optional — ``None`` means no limit.

    Attributes:
        cpu_seconds: Maximum CPU time in seconds (default 300 / 5 min).
        memory_mb: Maximum address space in MB (default 4096 / 4 GB).
        file_size_mb: Maximum file write size in MB (default 1024 / 1 GB).
        processes: Maximum number of child processes (default 100).
        timeout_seconds: Total wall-clock timeout in seconds (default 3600 / 1 h).
    """

    cpu_seconds: int | None = 300
    memory_mb: int | None = 4096
    file_size_mb: int | None = 1024
    processes: int | None = 100
    timeout_seconds: int | None = 3600


class ResourceGuard:
    """Enforces resource limits on command execution.

    Uses :func:`resource.setrlimit` to enforce limits at the OS level.
    Falls back to ``subprocess`` timeout on systems without ``setrlimit``.

    Args:
        limits: The :class:`ResourceLimits` to apply. Uses defaults if omitted.
    """

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self.limits = limits or ResourceLimits()

    def apply_limits(self) -> dict[str, object]:
        """Apply resource limits to the current process.

        Calls :func:`resource.setrlimit` for each configured limit.
        Skips limits that are ``None``.

        Returns:
            Dict of limits that were applied (for logging).
        """
        applied: dict[str, object] = {}
        limits = self.limits

        if limits.cpu_seconds is not None:
            try:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (limits.cpu_seconds, limits.cpu_seconds + 30),
                )
                applied["cpu_seconds"] = limits.cpu_seconds
            except (ValueError, resource.error) as e:
                logger.warning("Failed to set CPU limit: %s", e)

        if limits.memory_mb is not None:
            try:
                bytes_val = limits.memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (bytes_val, bytes_val))
                applied["memory_bytes"] = bytes_val
            except (ValueError, resource.error) as e:
                logger.warning("Failed to set memory limit: %s", e)

        if limits.file_size_mb is not None:
            try:
                bytes_val = limits.file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (bytes_val, bytes_val))
                applied["file_size_bytes"] = bytes_val
            except (ValueError, resource.error) as e:
                logger.warning("Failed to set file size limit: %s", e)

        if limits.processes is not None:
            try:
                resource.setrlimit(
                    resource.RLIMIT_NPROC,
                    (limits.processes, limits.processes),
                )
                applied["nproc"] = limits.processes
            except (ValueError, resource.error) as e:
                logger.warning("Failed to set process limit: %s", e)

        return applied

    def execute(
        self,
        cmd: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> sp.CompletedProcess[Any]:
        """Execute a command with resource limits.

        Uses :func:`subprocess.run` with ``timeout`` for basic protection.
        ``setrlimit`` is applied in the subprocess via ``preexec_fn``.

        Args:
            cmd: The command to execute (list form).
            cwd: Working directory for the subprocess.
            env: Environment variables for the subprocess. Inherits current
                environment if omitted.

        Returns:
            The :class:`subprocess.CompletedProcess` result.
        """
        timeout = self.limits.timeout_seconds

        def _preexec() -> None:
            self.apply_limits()

        try:
            result = sp.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                timeout=timeout,
                preexec_fn=_preexec if hasattr(resource, "setrlimit") else None,
            )
            return result
        except sp.TimeoutExpired:
            logger.error("Command timed out after %ss: %s", timeout, " ".join(cmd[:3]))
            return sp.CompletedProcess(
                cmd,
                -1,
                b"",
                f"TIMEOUT after {timeout}s".encode(),
            )
        except sp.CalledProcessError as e:
            return sp.CompletedProcess(
                cmd,
                e.returncode,
                e.stdout if e.stdout else b"",
                e.stderr if e.stderr else b"",
            )
