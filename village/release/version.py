"""Version computation for automated releases."""

import subprocess
from typing import Literal

BumpType = Literal["major", "minor", "patch", "none"]
BUMP_PRIORITY = {"major": 3, "minor": 2, "patch": 1, "none": 0}
SCOPE_TO_BUMP: dict[str, BumpType] = {
    "fix": "patch",
    "feature": "minor",
    "config": "patch",
    "docs": "none",
    "test": "none",
    "refactor": "none",
}


def aggregate_bumps(bumps: list[BumpType]) -> BumpType:
    """Aggregate multiple bump types (highest wins)."""
    if not bumps:
        return "none"

    highest: BumpType = "none"
    for bump in bumps:
        if BUMP_PRIORITY.get(bump, 0) > BUMP_PRIORITY.get(highest, 0):
            highest = bump

    return highest


def scope_to_bump(scope: str) -> BumpType:
    """Convert task scope to bump type."""
    result = SCOPE_TO_BUMP.get(scope, "none")
    return result


def is_no_op_release(bumps: list[BumpType]) -> bool:
    """Return True when the aggregate of bumps results in no version change."""
    return aggregate_bumps(bumps) == "none"


def compute_next_version(bump: BumpType) -> str:
    """Compute next version string by applying bump to latest git tag.

    Runs ``git describe --tags --abbrev=0`` to find the current version tag,
    strips the leading "v", parses major.minor.patch and applies the bump.

    Returns the new version WITHOUT a "v" prefix (e.g. "1.2.0").

    Raises:
        ValueError: If git describe fails for an unexpected reason.
    """
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # No tags at all — start from scratch
        if "No names found" in stderr or "No tags can describe" in stderr or "fatal: No names" in stderr:
            defaults: dict[BumpType, str] = {
                "major": "1.0.0",
                "minor": "0.1.0",
                "patch": "0.0.1",
                "none": "0.0.0",
            }
            return defaults[bump]
        # Some other git error
        raise ValueError(f"git describe failed (rc={result.returncode}): {stderr}")

    tag = result.stdout.strip().lstrip("v")
    parts = tag.split(".")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse version from tag '{result.stdout.strip()}': expected vMAJOR.MINOR.PATCH")

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Non-integer version component in tag '{result.stdout.strip()}': {exc}") from exc

    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    # "none" — return current version unchanged
    return f"{major}.{minor}.{patch}"
