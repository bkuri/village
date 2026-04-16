"""CI build dispatch and public API."""

import logging
import time
from pathlib import Path
from typing import Literal

from village.ci_integration.base import _append_ci_event, get_ci_config
from village.ci_integration.github import _monitor_github_actions, _trigger_github_actions
from village.ci_integration.gitlab import _monitor_gitlab_ci, _trigger_gitlab_ci
from village.ci_integration.jenkins import _monitor_jenkins, _trigger_jenkins
from village.ci_integration.models import (
    BuildResult,
    BuildStatus,
    BuildTimeoutError,
    BuildTriggerError,
    CIIntegrationError,
    PlatformNotConfiguredError,
)

logger = logging.getLogger(__name__)


def trigger_build(
    task_id: str,
    platform: Literal["github_actions", "gitlab_ci", "jenkins"],
    config_path: Path,
) -> BuildResult:
    """
    Trigger a CI/CD build for the given task.

    Args:
        task_id: Task ID to trigger build for
        platform: CI platform to use (github_actions, gitlab_ci, jenkins)
        config_path: Path to village directory

    Returns:
        BuildResult with success status, build ID, and message

    Raises:
        PlatformNotConfiguredError: If platform credentials not configured
        BuildTriggerError: If build trigger fails
    """
    configs = get_ci_config(config_path)
    platform_config = configs.get(platform)

    if not platform_config or not platform_config.token:
        raise PlatformNotConfiguredError(f"{platform} not configured: missing token")

    try:
        if platform == "github_actions":
            result = _trigger_github_actions(task_id, platform_config)
        elif platform == "gitlab_ci":
            result = _trigger_gitlab_ci(task_id, platform_config)
        elif platform == "jenkins":
            result = _trigger_jenkins(task_id, platform_config)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Log build trigger event
        event_dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cmd": "ci_trigger",
            "task_id": task_id,
            "platform": platform,
            "build_id": result.build_id,
            "result": "ok" if result.success else "error",
            "message": result.message,
        }
        _append_ci_event(event_dict, config_path)

        return result

    except Exception as e:
        logger.error(f"Failed to trigger build on {platform}: {e}")
        raise BuildTriggerError(f"Build trigger failed: {e}") from e


def monitor_build(
    build_id: str,
    platform: Literal["github_actions", "gitlab_ci", "jenkins"],
    config_path: Path,
) -> BuildStatus:
    """
    Monitor a CI/CD build status.

    Args:
        build_id: Build ID to monitor
        platform: CI platform (github_actions, gitlab_ci, jenkins)
        config_path: Path to village directory

    Returns:
        BuildStatus with current status, URL, and logs

    Raises:
        BuildTimeoutError: If build monitoring times out
        CIIntegrationError: If monitoring fails
    """
    configs = get_ci_config(config_path)
    platform_config = configs.get(platform)

    if not platform_config:
        raise PlatformNotConfiguredError(f"{platform} not configured")

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time

            if elapsed > platform_config.timeout_seconds:
                raise BuildTimeoutError(
                    f"Build {build_id} timed out after {elapsed}s (timeout: {platform_config.timeout_seconds}s)"
                )

            if platform == "github_actions":
                status = _monitor_github_actions(build_id, platform_config)
            elif platform == "gitlab_ci":
                status = _monitor_gitlab_ci(build_id, platform_config)
            elif platform == "jenkins":
                status = _monitor_jenkins(build_id, platform_config)
            else:
                raise ValueError(f"Unknown platform: {platform}")

            if status.status in ("success", "failure"):
                # Log build completion event
                event_dict = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "cmd": "ci_monitor",
                    "build_id": build_id,
                    "platform": platform,
                    "status": status.status,
                    "result": "ok",
                }
                _append_ci_event(event_dict, config_path)

                return status

            # Wait before next poll
            time.sleep(platform_config.polling_interval_seconds)

    except BuildTimeoutError:
        raise
    except Exception as e:
        logger.error(f"Failed to monitor build {build_id}: {e}")
        raise CIIntegrationError(f"Build monitoring failed: {e}") from e


def update_task_on_failure(
    task_id: str,
    build_id: str,
    reason: str,
    config_path: Path,
) -> None:
    """
    Update task status on build failure.

    Args:
        task_id: Task ID to update
        build_id: Build ID that failed
        reason: Reason for failure
        config_path: Path to village directory

    Raises:
        CIIntegrationError: If update operation fails
    """
    try:
        # Log build failure event
        event_dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cmd": "ci_failure",
            "task_id": task_id,
            "build_id": build_id,
            "reason": reason,
            "result": "error",
        }
        _append_ci_event(event_dict, config_path)

        logger.info(f"Task {task_id} updated for build {build_id} failure: {reason}")

    except Exception as e:
        logger.error(f"Failed to update task {task_id} on build failure: {e}")
        raise CIIntegrationError(f"Task update failed: {e}") from e
