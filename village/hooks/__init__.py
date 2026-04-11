"""Git hook management for Village."""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

HOOK_NAME = "prepare-commit-msg"
HOOK_SOURCE = Path(__file__).parent / f"{HOOK_NAME}.sh"


def install_hooks(git_root: Path, *, dry_run: bool = False) -> bool:
    """Install Village git hooks into the repository.

    Args:
        git_root: Path to the git repository root.
        dry_run: If True, preview without installing.

    Returns:
        True if hooks were installed (or already up to date).
    """
    hooks_dir = git_root / ".git" / "hooks"
    hook_target = hooks_dir / HOOK_NAME

    if not HOOK_SOURCE.exists():
        logger.warning(f"Hook template not found: {HOOK_SOURCE}")
        return False

    if hook_target.exists():
        current_content = hook_target.read_text(encoding="utf-8")
        source_content = HOOK_SOURCE.read_text(encoding="utf-8")
        if current_content.strip() == source_content.strip():
            logger.debug(f"Hook already up to date: {hook_target}")
            return True

    if dry_run:
        logger.info(f"Would install hook: {hook_target}")
        return True

    hooks_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(HOOK_SOURCE), str(hook_target))
    hook_target.chmod(0o755)
    logger.info(f"Installed hook: {hook_target}")
    return True


def uninstall_hooks(git_root: Path, *, dry_run: bool = False) -> bool:
    """Remove Village git hooks from the repository.

    Args:
        git_root: Path to the git repository root.
        dry_run: If True, preview without removing.

    Returns:
        True if hooks were removed (or didn't exist).
    """
    hooks_dir = git_root / ".git" / "hooks"
    hook_target = hooks_dir / HOOK_NAME

    if not hook_target.exists():
        logger.debug(f"Hook not installed: {hook_target}")
        return True

    if dry_run:
        logger.info(f"Would remove hook: {hook_target}")
        return True

    hook_target.unlink()
    logger.info(f"Removed hook: {hook_target}")
    return True
