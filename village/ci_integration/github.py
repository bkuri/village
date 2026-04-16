"""GitHub Actions CI integration."""

import json
import os
import subprocess
from typing import Literal, cast

from village.ci_integration.models import BuildResult, BuildStatus, CIPlatformConfig


def _trigger_github_actions(task_id: str, config: CIPlatformConfig) -> BuildResult:
    """
    Trigger GitHub Actions workflow.

    Args:
        task_id: Task ID
        config: Platform configuration

    Returns:
        BuildResult with build ID and message
    """
    try:
        cmd = [
            "gh",
            "workflow",
            "run",
            f"ci-{task_id}.yml",
            "-f",
            f"task_id={task_id}",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GH_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildResult(
                success=False,
                build_id="",
                platform="github_actions",
                message=f"gh workflow failed: {result.stderr}",
            )

        # Extract run ID from output
        build_id = result.stdout.strip()

        return BuildResult(
            success=True,
            build_id=build_id,
            platform="github_actions",
            message=f"GitHub Actions workflow triggered: {build_id}",
        )

    except subprocess.TimeoutExpired:
        return BuildResult(
            success=False,
            build_id="",
            platform="github_actions",
            message="Command timed out",
        )
    except FileNotFoundError:
        return BuildResult(
            success=False,
            build_id="",
            platform="github_actions",
            message="gh CLI not found",
        )


def _monitor_github_actions(build_id: str, config: CIPlatformConfig) -> BuildStatus:
    """
    Monitor GitHub Actions workflow run.

    Args:
        build_id: Build/run ID
        config: Platform configuration

    Returns:
        BuildStatus with current status
    """
    try:
        cmd = ["gh", "run", "view", build_id, "--json", "status,conclusion,logsUrl,databaseId"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GH_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildStatus(status="pending", url=None, logs=result.stderr)

        data = json.loads(result.stdout)

        gh_status = data.get("status", "queued")
        conclusion = data.get("conclusion")

        # Map GitHub status to our status
        if conclusion == "success":
            status = "success"
        elif conclusion in ("failure", "cancelled"):
            status = "failure"
        elif gh_status == "queued":
            status = "pending"
        elif gh_status == "in_progress":
            status = "running"
        else:
            status = "pending"

        return BuildStatus(
            status=cast(Literal["pending", "running", "success", "failure"], status),
            url=data.get("logsUrl"),
            logs=None,
        )

    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return BuildStatus(status="pending", url=None, logs=None)
