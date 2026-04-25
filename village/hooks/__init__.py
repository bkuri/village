"""Git hook management for Village.

Supports both git and jj (Jujutsu) repositories:
- git: hooks installed to ``.git/hooks/``
- jj colocated: same as git (shares ``.git/hooks/``)
- jj native: hooks installed to ``.jj/repo/hooks/``
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

HOOKS_DIR = Path(__file__).parent

# All hooks Village manages. Each maps to a .sh template in this package.
MANAGED_HOOKS = (
    "prepare-commit-msg",
    "pre-commit",
    "pre-tag",
)

# Marker written at the top of Village-managed hooks so we can identify
# our own hooks and avoid overwriting user-created hooks.
VILLAGE_MARKER = "Installed by: village"


def _is_village_hook(hook_path: Path) -> bool:
    """Check if an existing hook was installed by Village."""
    if not hook_path.exists():
        return False
    content = hook_path.read_text(encoding="utf-8")
    return VILLAGE_MARKER in content


def _hook_source(hook_name: str) -> Path:
    """Return the template path for a hook."""
    return HOOKS_DIR / f"{hook_name}.sh"


def _resolve_hooks_dir(project_root: Path) -> Path:
    """Resolve the hooks directory for the project.

    Checks for git first, then jj native, then falls back to git.

    Priority:
    1. ``.git/hooks/`` — git or jj colocated repos
    2. ``.jj/repo/hooks/`` — jj native (non-colocated) repos
    """
    git_hooks = project_root / ".git" / "hooks"
    if (project_root / ".git").is_dir():
        return git_hooks

    jj_hooks = project_root / ".jj" / "repo" / "hooks"
    if (project_root / ".jj").is_dir():
        return jj_hooks

    # Default to git — will be created on install.
    return git_hooks


def install_hooks(project_root: Path, *, dry_run: bool = False) -> bool:
    """Install Village hooks into the repository.

    Installs all hooks from MANAGED_HOOKS. Skips hooks that are already
    up to date. Replaces Village-managed hooks that have changed.
    Warns (and skips) if a non-Village hook with the same name exists.

    Works with git, jj colocated, and jj native repos.

    Args:
        project_root: Path to the project/repository root.
        dry_run: If True, preview without installing.

    Returns:
        True if all hooks were installed (or already up to date).
    """
    hooks_dir = _resolve_hooks_dir(project_root)
    all_ok = True

    for hook_name in MANAGED_HOOKS:
        source = _hook_source(hook_name)
        hook_target = hooks_dir / hook_name

        if not source.exists():
            logger.warning(f"Hook template not found: {source}")
            all_ok = False
            continue

        source_content = source.read_text(encoding="utf-8")

        if hook_target.exists():
            # Skip if it's not our hook — don't overwrite user hooks.
            if not _is_village_hook(hook_target):
                logger.warning(
                    f"Hook {hook_name} exists but is not Village-managed. Skipping. "
                    f"Remove it manually to install Village's version."
                )
                all_ok = False
                continue

            current_content = hook_target.read_text(encoding="utf-8")
            if current_content.strip() == source_content.strip():
                logger.debug(f"Hook already up to date: {hook_target}")
                continue

        if dry_run:
            logger.info(f"Would install hook: {hook_target}")
            continue

        hooks_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(hook_target))
        hook_target.chmod(0o755)
        logger.info(f"Installed hook: {hook_target}")

    return all_ok


def uninstall_hooks(project_root: Path, *, dry_run: bool = False) -> bool:
    """Remove Village hooks from the repository.

    Only removes hooks that were installed by Village (identified by
    the VILLAGE_MARKER). Non-Village hooks are left untouched.

    Works with git, jj colocated, and jj native repos.

    Args:
        project_root: Path to the project/repository root.
        dry_run: If True, preview without removing.

    Returns:
        True if all Village hooks were removed (or didn't exist).
    """
    hooks_dir = _resolve_hooks_dir(project_root)
    all_ok = True

    for hook_name in MANAGED_HOOKS:
        hook_target = hooks_dir / hook_name

        if not hook_target.exists():
            logger.debug(f"Hook not installed: {hook_target}")
            continue

        if not _is_village_hook(hook_target):
            logger.warning(f"Hook {hook_name} exists but is not Village-managed. Not removing.")
            all_ok = False
            continue

        if dry_run:
            logger.info(f"Would remove hook: {hook_target}")
            continue

        hook_target.unlink()
        logger.info(f"Removed hook: {hook_target}")

    return all_ok
