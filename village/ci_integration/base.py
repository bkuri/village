"""Shared CI integration base logic."""

import json
import logging
import os
from pathlib import Path

from village.ci_integration.models import CIPlatformConfig

logger = logging.getLogger(__name__)


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
    gitlab_url = os.environ.get("GITLAB_URL") or os.environ.get("VILLAGE_GITLAB_URL", "https://gitlab.com")
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
