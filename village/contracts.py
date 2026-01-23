"""Resume contract generation."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from village.config import Config, get_config

logger = logging.getLogger(__name__)

CONTRACT_VERSION = 1


@dataclass
class ResumeContract:
    """Resume contract for OpenCode."""

    task_id: str
    agent: str
    worktree_path: Path
    git_root: Path
    window_name: str
    claimed_at: datetime
    version: int = CONTRACT_VERSION
    village_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.village_dir is None:
            config = get_config()
            self.village_dir = config.village_dir


def generate_contract(
    task_id: str,
    agent: str,
    worktree_path: Path,
    window_name: str,
    config: Optional[Config] = None,
) -> ResumeContract:
    """
    Generate a resume contract.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        agent: Agent name (e.g., "build", "frontend")
        worktree_path: Path to worktree directory
        window_name: Tmux window name (e.g., "build-1-bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        ResumeContract object
    """
    if config is None:
        config = get_config()

    logger.debug(
        f"Generating contract: task_id={task_id}, agent={agent}, "
        f"worktree_path={worktree_path}, window_name={window_name}"
    )

    return ResumeContract(
        task_id=task_id,
        agent=agent,
        worktree_path=worktree_path,
        git_root=config.git_root,
        window_name=window_name,
        claimed_at=datetime.now(),
        village_dir=config.village_dir,
    )


def format_contract_for_stdin(contract: ResumeContract) -> str:
    """
    Format contract for stdin injection.

    Creates a JSON string suitable for piping to OpenCode via stdin.

    Args:
        contract: ResumeContract object

    Returns:
        JSON string (single line, no pretty-printing)
    """
    contract_dict = {
        "version": contract.version,
        "task_id": contract.task_id,
        "agent": contract.agent,
        "worktree_path": str(contract.worktree_path),
        "git_root": str(contract.git_root),
        "window_name": contract.window_name,
        "claimed_at": contract.claimed_at.isoformat(),
        "village_dir": str(contract.village_dir) if contract.village_dir else None,
    }

    return json.dumps(contract_dict, sort_keys=True)


def format_contract_as_html(contract: ResumeContract) -> str:
    """
    Format contract as minimal HTML output.

    Creates a self-contained HTML document with JSON metadata in a script tag.

    HTML format:
    ```html
    <pre>
    <script type="application/json" id="village-meta">
    {JSON metadata}
    </script>
    </pre>
    ```

    Args:
        contract: ResumeContract object

    Returns:
        HTML string with embedded JSON metadata
    """
    metadata = {
        "version": contract.version,
        "task_id": contract.task_id,
        "agent": contract.agent,
        "worktree_path": str(contract.worktree_path),
        "git_root": str(contract.git_root),
        "window_name": contract.window_name,
        "claimed_at": contract.claimed_at.isoformat(),
        "village_dir": str(contract.village_dir) if contract.village_dir else None,
    }

    # Format JSON with 2-space indentation
    json_metadata = json.dumps(metadata, sort_keys=True, indent=2)

    # Minimal HTML structure
    html = f"""<pre>
<script type="application/json" id="village-meta">
{json_metadata}
</script>
</pre>"""

    logger.debug(f"Generated HTML contract for task_id={contract.task_id}")
    return html


def contract_to_dict(contract: ResumeContract) -> dict[str, str | None]:
    """
    Convert contract to dictionary.

    Args:
        contract: ResumeContract object

    Returns:
        Dictionary representation
    """
    return {
        "version": str(contract.version),
        "task_id": contract.task_id,
        "agent": contract.agent,
        "worktree_path": str(contract.worktree_path),
        "git_root": str(contract.git_root),
        "window_name": contract.window_name,
        "claimed_at": contract.claimed_at.isoformat(),
        "village_dir": str(contract.village_dir) if contract.village_dir else None,
    }
