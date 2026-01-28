"""Beads CLI client for LLM chat integration."""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from village.chat.task_spec import TaskSpec

logger = logging.getLogger(__name__)


class BeadsError(Exception):
    """Raised when Beads CLI command fails."""

    pass


@dataclass
class BeadsClient:
    """Wrapper for Beads CLI commands."""

    def __init__(self) -> None:
        """Initialize BeadsClient."""
        self._bd_cmd = "bd"

    def _to_beads_spec(self, spec: TaskSpec) -> dict[str, object]:
        """
        Convert TaskSpec to dict format for Beads CLI.

        Args:
            spec: TaskSpec instance

        Returns:
            Dictionary with fields for Beads create command
        """
        return {
            "title": spec.title,
            "description": spec.description,
            "estimate": spec.estimate,
        }

    async def search_tasks(
        self, query: str, limit: int = 5, status: str = "open"
    ) -> list[dict[str, object]]:
        """
        Search for tasks in Beads.

        Args:
            query: Search query string
            limit: Maximum number of results
            status: Filter by task status

        Returns:
            List of task dictionaries

        Raises:
            BeadsError: If command fails
        """
        cmd = [
            self._bd_cmd,
            "list",
            "--json",
            "--title",
            query,
            "--status",
            status,
            "--limit",
            str(limit),
        ]

        result = await self._run_command(cmd)

        try:
            tasks = json.loads(result.stdout)
            if not isinstance(tasks, list):
                raise BeadsError(f"Expected list from bd list, got {type(tasks)}")
            return tasks
        except json.JSONDecodeError as e:
            raise BeadsError(f"Failed to parse Beads response: {e}") from e

    async def create_task(self, spec: TaskSpec) -> str:
        """
        Create a new task in Beads.

        Args:
            spec: Task specification

        Returns:
            Created task ID (format: bd-xxxx)

        Raises:
            BeadsError: If command fails
        """
        cmd = [
            self._bd_cmd,
            "create",
            spec.title,
            "--description",
            spec.description,
        ]

        deps_parts = []
        if spec.blocks:
            deps_parts.append(f"blocks:{','.join(spec.blocks)}")
        if spec.blocked_by:
            deps_parts.append(f"blocked_by:{','.join(spec.blocked_by)}")

        if deps_parts:
            deps_str = ",".join(deps_parts)
            cmd.extend(["--deps", deps_str])

        result = await self._run_command(cmd)

        task_id = self._extract_task_id(result.stdout)
        if not task_id:
            raise BeadsError(f"Could not extract task ID from output: {result.stdout}")

        return task_id

    async def get_dependencies(self, task_id: str) -> dict[str, object]:
        """
        Get dependencies for a task.

        Args:
            task_id: Task ID to query

        Returns:
            Dictionary with dependency information

        Raises:
            BeadsError: If command fails
        """
        cmd = [
            self._bd_cmd,
            "dep",
            "list",
            task_id,
            "--json",
        ]

        result = await self._run_command(cmd)

        try:
            deps = json.loads(result.stdout)
            if not isinstance(deps, dict):
                raise BeadsError(f"Expected dict from bd dep list, got {type(deps)}")
            return deps
        except json.JSONDecodeError as e:
            raise BeadsError(f"Failed to parse Beads response: {e}") from e

    def parse_estimate(self, estimate_str: str) -> int:
        """
        Parse estimate string to minutes.

        Supports formats:
        - "2-3 hours" → 120-180 (returns average)
        - "2 hours" → 120
        - "30 min" → 30
        - "1.5 days" → 720

        Args:
            estimate_str: Estimate string (e.g., "2-3 hours", "30 min")

        Returns:
            Estimate in minutes

        Raises:
            BeadsError: If estimate string is invalid
        """
        estimate_str = estimate_str.strip().lower()

        if not estimate_str:
            raise BeadsError("Empty estimate string")

        hour_pattern = r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*hours?\b"
        range_match = re.search(hour_pattern, estimate_str)

        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return int((low + high) / 2 * 60)

        hour_pattern_alt = r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*hrs?\b"
        range_match = re.search(hour_pattern_alt, estimate_str)

        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return int((low + high) / 2 * 60)

        single_pattern = r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|days?|d|weeks?|w)"
        match = re.search(single_pattern, estimate_str)

        if not match:
            raise BeadsError(f"Invalid estimate format: {estimate_str}")

        value = float(match.group(1))
        unit = match.group(2)

        multipliers = {
            "h": 60,
            "hr": 60,
            "hrs": 60,
            "hour": 60,
            "hours": 60,
            "m": 1,
            "min": 1,
            "mins": 1,
            "minute": 1,
            "minutes": 1,
            "d": 8 * 60,
            "day": 8 * 60,
            "days": 8 * 60,
            "w": 5 * 8 * 60,
            "week": 5 * 8 * 60,
            "weeks": 5 * 8 * 60,
        }

        if unit not in multipliers:
            raise BeadsError(f"Unknown estimate unit: {unit}")

        return int(value * multipliers[unit])

    def parse_estimate_to_minutes(self, estimate: str) -> int:
        """
        Parse estimate string to minutes.

        Supports formats:
        - "2-3 hours" → 120-180 (returns average)
        - "2 hours" → 120
        - "30 min" → 30
        - "1.5 days" → 720

        Args:
            estimate: Estimate string (e.g., "2-3 hours", "30 min")

        Returns:
            Estimate in minutes

        Raises:
            BeadsError: If estimate string is invalid
        """
        return self.parse_estimate(estimate)

    def _extract_task_id(self, output: str) -> Optional[str]:
        """
        Extract task ID from Beads output.

        Args:
            output: Command output text

        Returns:
            Task ID if found, None otherwise
        """
        patterns = [
            r"(bd-[a-z0-9]{4,})",
            r"created:\s*(bd-[a-z0-9]+)",
            r"task\s+id:\s*(bd-[a-z0-9]+)",
            r"id:\s*(bd-[a-z0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        return None

    async def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """
        Run a Beads CLI command.

        Args:
            cmd: Command and arguments

        Returns:
            Completed process with stdout/stderr

        Raises:
            BeadsError: If command fails
        """
        logger.debug(f"Running Beads command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_msg = f"Beads command failed: {' '.join(cmd)}"
            if result.stderr:
                error_msg += f"\n{result.stderr}"
            logger.error(error_msg)
            raise BeadsError(error_msg)

        logger.debug(f"Beads command succeeded (exit {result.returncode})")
        return result
