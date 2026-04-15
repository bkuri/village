"""Project name derivation for task labels.

Derives project names from onboarding config or normalized project path.
Used to scope tasks across multiple active projects.
"""

import re
from pathlib import Path
from typing import Any

from village.config import Config


def sanitize_project_name(name: str) -> str:
    """Sanitize a project name for use as a label.

    - Lowercase
    - Replace spaces/special chars with hyphens
    - Collapse multiple hyphens
    - Strip leading/trailing hyphens
    - Max 50 chars
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9/]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name[:50]


def normalize_project_path(project_path: Path, base_path: Path | None = None) -> str:
    """Normalize a project path to a relative label-friendly string.

    Args:
        project_path: The project's root directory
        base_path: The base directory to strip (defaults to parent of project_path)

    Returns:
        Normalized relative path string

    Examples:
        >>> normalize_project_path(Path("/home/bk/source/village"))
        "village"
        >>> normalize_project_path(Path("/home/bk/source/code/my-app"), Path("/home/bk/source"))
        "code/my-app"
    """
    if base_path is None:
        base_path = project_path.parent

    try:
        relative = project_path.relative_to(base_path)
        return str(relative)
    except ValueError:
        # project_path is not under base_path, use basename
        return project_path.name


def get_project_name(config: Config | None = None, project_path: Path | None = None) -> str:
    """Derive project name for task labels.

    Priority:
    1. Onboarding project name from config
    2. Normalized project path

    Args:
        config: Village config (optional, reads global if not provided)
        project_path: Project root path (optional, uses cwd if not provided)

    Returns:
        Sanitized project name suitable for labels
    """
    if project_path is None:
        project_path = Path.cwd()

    # Try onboarding project name first
    if config is not None:
        project_name = getattr(config, "project_name", None) or getattr(config, "project", None)
        if project_name:
            return sanitize_project_name(project_name)

    # Try reading from onboarding config section
    try:
        if config is not None:
            onboard_config = getattr(config, "onboard", None)
            if onboard_config:
                name = getattr(onboard_config, "project_name", None)
                if name:
                    return sanitize_project_name(name)
    except Exception:
        pass

    # Fallback to normalized path
    # Determine base path: typically the parent of git root
    base_path = project_path.parent
    normalized = normalize_project_path(project_path, base_path)
    return sanitize_project_name(normalized)


def make_project_label(project_name: str) -> str:
    """Create a project label string.

    Args:
        project_name: The sanitized project name

    Returns:
        Label in format "project:<name>"
    """
    return f"project:{project_name}"


def extract_project_from_label(label: str) -> str | None:
    """Extract project name from a label string.

    Args:
        label: A label string

    Returns:
        Project name if label is a project label, None otherwise
    """
    if label.startswith("project:"):
        return label[len("project:") :]
    return None


def filter_by_project(
    items: list[dict[str, Any]], project_name: str, labels_key: str = "labels"
) -> list[dict[str, Any]]:
    """Filter items by project label.

    Args:
        items: List of dicts with a labels key
        project_name: Project name to filter by
        labels_key: Key name for labels list

    Returns:
        Filtered list
    """
    label = f"project:{project_name}"
    return [item for item in items if label in item.get(labels_key, [])]
