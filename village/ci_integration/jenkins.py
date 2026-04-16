"""Jenkins CI integration."""

import json
import os
import subprocess
from typing import Literal, cast

from village.ci_integration.models import BuildResult, BuildStatus, CIPlatformConfig


def _trigger_jenkins(task_id: str, config: CIPlatformConfig) -> BuildResult:
    """
    Trigger Jenkins build.

    Args:
        task_id: Task ID
        config: Platform configuration

    Returns:
        BuildResult with build ID and message
    """
    try:
        if not config.url:
            return BuildResult(
                success=False,
                build_id="",
                platform="jenkins",
                message="Jenkins URL not configured",
            )

        cmd = [
            "jenkins-cli",
            "build",
            "--url",
            config.url,
            "--token",
            config.token or "",
            "--param",
            f"TASK_ID={task_id}",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "JENKINS_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildResult(
                success=False,
                build_id="",
                platform="jenkins",
                message=f"jenkins-cli build failed: {result.stderr}",
            )

        # Extract build number from output
        build_id = result.stdout.strip()

        return BuildResult(
            success=True,
            build_id=build_id,
            platform="jenkins",
            message=f"Jenkins build triggered: {build_id}",
        )

    except subprocess.TimeoutExpired:
        return BuildResult(
            success=False,
            build_id="",
            platform="jenkins",
            message="Command timed out",
        )
    except FileNotFoundError:
        return BuildResult(
            success=False,
            build_id="",
            platform="jenkins",
            message="jenkins-cli not found",
        )


def _monitor_jenkins(build_id: str, config: CIPlatformConfig) -> BuildStatus:
    """
    Monitor Jenkins build.

    Args:
        build_id: Build number
        config: Platform configuration

    Returns:
        BuildStatus with current status
    """
    try:
        if not config.url:
            return BuildStatus(status="pending", url=None, logs="Jenkins URL not configured")

        cmd = [
            "jenkins-cli",
            "build-info",
            "--url",
            config.url,
            "--token",
            config.token or "",
            build_id,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "JENKINS_TOKEN": config.token or ""},
        )

        if result.returncode != 0:
            return BuildStatus(status="pending", url=None, logs=result.stderr)

        # Parse Jenkins build result
        data = json.loads(result.stdout)

        result_status = data.get("result", "PENDING").upper()

        # Map Jenkins status to our status
        if result_status == "SUCCESS":
            status = "success"
        elif result_status in ("FAILURE", "ABORTED"):
            status = "failure"
        else:
            status = "running"

        return BuildStatus(
            status=cast(Literal["pending", "running", "success", "failure"], status),
            url=f"{config.url}/job/{build_id}",
            logs=None,
        )

    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return BuildStatus(status="pending", url=None, logs=None)
