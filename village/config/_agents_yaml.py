import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AgentRole:
    """Configuration for a single agent role with git identity and permissions."""

    git_user: str
    git_email: str
    remote_key: str | None = None  # path to SSH private key
    allowed_paths: list[str] | None = None  # ["src/**", "tests/**"]
    allowed_operations: list[str] | None = None  # ["commit", "push", "tag"]


@dataclass
class AgentsYamlConfig:
    """Configuration loaded from .village/agents.yaml.

    Defines per-role git identities and permissions for execution engine agents.
    """

    version: int = 1
    roles: dict[str, AgentRole] | None = None  # keyed by role name

    @classmethod
    def default_roles(cls) -> dict[str, AgentRole]:
        """Return the built-in default roles."""
        return {
            "planner": AgentRole(
                git_user="Village Planner",
                git_email="planner@village.local",
                remote_key=None,
                allowed_paths=None,  # all paths
                allowed_operations=["commit", "push", "tag"],
            ),
            "builder": AgentRole(
                git_user="Village Builder",
                git_email="builder@village.local",
                remote_key=None,
                allowed_paths=["src/**", "tests/**"],
                allowed_operations=["commit", "push", "tag"],
            ),
            "release": AgentRole(
                git_user="Village Release",
                git_email="release@village.local",
                remote_key=None,
                allowed_paths=[],  # no direct file access
                allowed_operations=["tag", "push-tag"],
            ),
        }


def load_agents_yaml(path: Path) -> AgentsYamlConfig | None:
    """Load agent role configuration from a YAML file.

    Returns None if the file does not exist or is invalid.
    Merges loaded roles with defaults (explicit roles override defaults).
    """
    if not path.exists():
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        return load_agents_yaml_from_string(raw)
    except Exception as e:
        logger.warning(f"Failed to load agents.yaml from {path}: {e}")
        return None


def load_agents_yaml_from_string(yaml_content: str) -> AgentsYamlConfig | None:
    """Load agent role configuration from a YAML string."""
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            logger.warning("agents.yaml content is not a mapping")
            return None
        return _parse_agents_yaml(data)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse agents.yaml: {e}")
        return None


def _parse_agents_yaml(data: dict[str, object]) -> AgentsYamlConfig | None:
    """Parse a raw dict into an AgentsYamlConfig."""
    version = data.get("version", 1)
    if not isinstance(version, int) or version < 1:
        logger.warning(f"Invalid agents.yaml version: {version}, expected int >= 1")
        return None

    roles: dict[str, AgentRole] = {}
    roles_raw = data.get("roles")
    if roles_raw is not None and isinstance(roles_raw, dict):
        for role_name, role_data in roles_raw.items():
            if isinstance(role_data, dict):
                roles[role_name] = AgentRole(
                    git_user=role_data.get("git_user", ""),
                    git_email=role_data.get("git_email", ""),
                    remote_key=role_data.get("remote_key"),
                    allowed_paths=role_data.get("allowed_paths"),
                    allowed_operations=role_data.get("allowed_operations"),
                )

    return AgentsYamlConfig(version=version, roles=roles or None)
