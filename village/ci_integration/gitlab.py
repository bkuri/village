"""GitLab CI integration."""

import os
import subprocess
from typing import Literal, cast

from village.ci_integration.models import BuildResult, BuildStatus, CIPlatformConfig


def _trigger_gitlab_ci(task_id: str, config: CIPlatformConfig) -> BuildResult:
    """
    Trigger GitLab CI pipeline.

    Args:
        task_id: Task ID
        config: Platform configuration

    Returns:
        BuildResult with build ID and message
    """
    try:
        cmd = [
            "gitlab-ci",
            "trigger",
            "--token",
            config.token or "",
            "--variable",
            f"TASK_ID={task_id}",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GITLAB_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildResult(
                success=False,
                build_id="",
                platform="gitlab_ci",
                message=f"gitlab-ci trigger failed: {result.stderr}",
            )

        # Extract pipeline ID from output
        build_id = result.stdout.strip()

        return BuildResult(
            success=True,
            build_id=build_id,
            platform="gitlab_ci",
            message=f"GitLab CI pipeline triggered: {build_id}",
        )

    except subprocess.TimeoutExpired:
        return BuildResult(
            success=False,
            build_id="",
            platform="gitlab_ci",
            message="Command timed out",
        )
    except FileNotFoundError:
        return BuildResult(
            success=False,
            build_id="",
            platform="gitlab_ci",
            message="gitlab-ci CLI not found",
        )


def _monitor_gitlab_ci(build_id: str, config: CIPlatformConfig) -> BuildStatus:
    """
    Monitor GitLab CI pipeline.

    Args:
        build_id: Pipeline ID
        config: Platform configuration

    Returns:
        BuildStatus with current status
    """
    try:
        cmd = ["gitlab-ci", "status", build_id, "--token", config.token or ""]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GITLAB_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildStatus(status="pending", url=None, logs=result.stderr)

        status_output = result.stdout.strip().lower()

        # Map GitLab status to our status
        if "success" in status_output:
            status = "success"
        elif "failed" in status_output or "canceled" in status_output:
            status = "failure"
        elif "running" in status_output:
            status = "running"
        elif "pending" in status_output:
            status = "pending"
        else:
            status = "pending"

        return BuildStatus(
            status=cast(Literal["pending", "running", "success", "failure"], status),
            url=f"{config.url}/pipelines/{build_id}",
            logs=None,
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return BuildStatus(status="pending", url=None, logs=None)
