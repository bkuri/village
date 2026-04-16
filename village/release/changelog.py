"""Changelog management for automated releases."""

import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from village.release.queue import PendingBump
from village.release.version import BumpType

logger = logging.getLogger(__name__)

ChangelogCategory = Literal["Added", "Changed", "Fixed", "Breaking"]
TASK_TYPE_TO_CATEGORY: dict[str, ChangelogCategory] = {
    "bug": "Fixed",
    "feature": "Added",
    "task": "Changed",
    "chore": "Changed",
    "epic": "Changed",
}


def get_changelog_category(task_type: str, bump: BumpType) -> ChangelogCategory:
    """Map task type and bump to changelog category.

    Breaking changes (bump:major) always go to Breaking section.
    Otherwise, use task type mapping.
    """
    if bump == "major":
        return "Breaking"
    return TASK_TYPE_TO_CATEGORY.get(task_type, "Changed")


def update_changelog(version: str, pending: list[PendingBump]) -> None:
    """Insert a new changelog section for *version* with categorized entries.

    Locates CHANGELOG.md relative to the git repository root.  The new
    section is inserted after the last ``## [Unreleased]`` block (i.e. just
    before the first ``## [X.Y.Z]`` line).  Tasks with bump type "none" are
    excluded from the entry.

    Entries are categorized into:
    - Added: New features
    - Changed: Enhancements, refactors
    - Fixed: Bug fixes
    - Breaking: Breaking changes (bump:major)

    Falls back to appending at the end of the file if the expected structure
    is not found, or creates the file if it doesn't exist.

    The write is performed atomically (temp-file + rename).
    """
    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_root_result.returncode == 0:
        git_root = Path(git_root_result.stdout.strip())
    else:
        git_root = Path.cwd()

    changelog_path = git_root / "CHANGELOG.md"

    today = datetime.now().strftime("%Y-%m-%d")

    # Filter out bump:none and categorize
    non_trivial = [p for p in pending if p.bump != "none"]

    if not non_trivial:
        logger.info(f"No non-trivial changes for version {version}, skipping changelog update")
        return

    # Group by category
    categories: dict[ChangelogCategory, list[PendingBump]] = {
        "Breaking": [],
        "Added": [],
        "Changed": [],
        "Fixed": [],
    }

    for p in non_trivial:
        category = get_changelog_category(p.task_type, p.bump)
        categories[category].append(p)

    # Build the new section
    section_lines = [f"## [{version}] - {today}", ""]

    category_order: list[ChangelogCategory] = ["Breaking", "Added", "Changed", "Fixed"]
    for category in category_order:
        items = categories[category]
        if items:
            section_lines.append(f"### {category}")
            for p in items:
                title = p.title or p.task_id
                section_lines.append(f"- {title} (`{p.task_id}`)")
            section_lines.append("")

    new_section = "\n".join(section_lines) + "\n"

    if not changelog_path.exists():
        changelog_path.write_text(new_section, encoding="utf-8")
        logger.info(f"Created {changelog_path} with version {version}")
        return

    content = changelog_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Find the first versioned section header (## [X.Y.Z]) — insert before it
    insert_at: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## [") and not stripped.startswith("## [Unreleased"):
            insert_at = i
            break

    if insert_at is not None:
        lines.insert(insert_at, new_section + "\n")
    else:
        # Append at the end
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append("\n" + new_section)

    new_content = "".join(lines)

    # Atomic write via temp file + rename
    dir_ = changelog_path.parent
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp", encoding="utf-8") as tmp:
        tmp.write(new_content)
        tmp_path = Path(tmp.name)

    tmp_path.replace(changelog_path)
    logger.info(f"Updated {changelog_path} with version {version}")
