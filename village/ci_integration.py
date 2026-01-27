"""CI/CD integration for build triggering and monitoring."""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

logger = logging.getLogger(__name__)


class CIIntegrationError(Exception):
    """Base exception for CI integration errors."""


class BuildTriggerError(CIIntegrationError):
    """Exception raised when build triggering fails."""


class BuildTimeoutError(CIIntegrationError):
    """Exception raised when build monitoring times out."""


class PlatformNotConfiguredError(CIIntegrationError):
    """Exception raised when CI platform is not configured."""


@dataclass
class BuildResult:
    """Result of a build trigger operation."""

    success: bool
    build_id: str
    platform: str
    message: str


@dataclass
class BuildStatus:
    """Status of a running build."""

    status: Literal["pending", "running", "success", "failure"]
    url: str | None
    logs: str | None


@dataclass
class CIPlatformConfig:
    """Configuration for a CI/CD platform."""

    token: str | None
    url: str | None
    polling_interval_seconds: int = 30
    timeout_seconds: int = 3600


def get_ci_config(config_path: Path) -> dict[str, CIPlatformConfig]:
    """
    Load CI platform configurations from environment and config file.

    Args:
        config_path: Path to village directory

    Returns:
        Dict mapping platform names to their configs
    """
    configs: dict[str, CIPlatformConfig] = {}

    # GitHub Actions config
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("VILLAGE_GITHUB_TOKEN")
    github_url = os.environ.get("GITHUB_API_URL") or os.environ.get("VILLAGE_GITHUB_URL")
    configs["github_actions"] = CIPlatformConfig(
        token=github_token,
        url=github_url,
        polling_interval_seconds=int(os.environ.get("VILLAGE_GITHUB_POLLING_INTERVAL", "30")),
        timeout_seconds=int(os.environ.get("VILLAGE_GITHUB_TIMEOUT", "3600")),
    )

    # GitLab CI config
    gitlab_token = os.environ.get("GITLAB_TOKEN") or os.environ.get("VILLAGE_GITLAB_TOKEN")
    gitlab_url = os.environ.get("GITLAB_URL") or os.environ.get(
        "VILLAGE_GITLAB_URL", "https://gitlab.com"
    )
    configs["gitlab_ci"] = CIPlatformConfig(
        token=gitlab_token,
        url=gitlab_url,
        polling_interval_seconds=int(os.environ.get("VILLAGE_GITLAB_POLLING_INTERVAL", "30")),
        timeout_seconds=int(os.environ.get("VILLAGE_GITLAB_TIMEOUT", "3600")),
    )

    # Jenkins config
    jenkins_token = os.environ.get("JENKINS_TOKEN") or os.environ.get("VILLAGE_JENKINS_TOKEN")
    jenkins_url = os.environ.get("JENKINS_URL") or os.environ.get("VILLAGE_JENKINS_URL")
    configs["jenkins"] = CIPlatformConfig(
        token=jenkins_token,
        url=jenkins_url,
        polling_interval_seconds=int(os.environ.get("VILLAGE_JENKINS_POLLING_INTERVAL", "30")),
        timeout_seconds=int(os.environ.get("VILLAGE_JENKINS_TIMEOUT", "3600")),
    )

    return configs


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
                    f"Build {build_id} timed out after {elapsed}s "
                    f"(timeout: {platform_config.timeout_seconds}s)"
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


def _append_ci_event(event_dict: dict[str, str], config_path: Path) -> None:
    """
    Append CI event to log file.

    Args:
        event_dict: Event data dictionary
        config_path: Path to village directory
    """
    event_log_path = config_path / "events.log"

    try:
        event_log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(event_log_path, "a", encoding="utf-8") as f:
            event_json = json.dumps(event_dict, sort_keys=True)
            f.write(event_json + "\n")
            f.flush()

        logger.debug(f"Logged CI event: {event_dict.get('cmd')} {event_dict.get('task_id', '')}")

    except IOError as e:
        logger.error(f"Failed to write CI event to {event_log_path}: {e}")
        raise
