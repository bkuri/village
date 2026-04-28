import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ApprovalManifest:
    """Per-spec approval manifest defining what the agent is allowed to do.

    Loaded from .village/approvals/<spec-id>.yaml.
    The builder reads manifests from git objects (not disk) for tamper-proofing.
    """

    version: int = 1
    spec_id: str = ""
    allowed_commands: list[str] | None = None  # ["pytest", "ruff", "git add", "git commit"]
    allowed_scripts: list[str] | None = None  # explicit filenames
    allowed_paths: list[str] | None = None  # ["src/**", "tests/**"]
    disallowed_content: list[str] | None = None  # additional per-spec patterns
    test_required: bool = True
    filename_casing: str | None = None  # overrides global


class ManifestStore:
    """Store and load approval manifests from the .village/approvals/ directory.

    Manifests are loaded from git objects for tamper-proofing during build,
    or from disk during development.
    """

    def __init__(self, approvals_dir: Path) -> None:
        self.approvals_dir = approvals_dir

    def load(self, spec_id: str, ref: str = "HEAD") -> ApprovalManifest | None:
        """Load a manifest from disk (or git ref) for the given spec_id.

        Args:
            spec_id: The spec identifier (without .yaml extension).
            ref: Git ref to load from (defaults to HEAD for disk checkout).

        Returns:
            ApprovalManifest or None if not found.
        """
        path = self.approvals_dir / f"{spec_id}.yaml"
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            return self._parse(raw, spec_id)
        except Exception as e:
            logger.warning(f"Failed to load manifest {spec_id} from {path}: {e}")
            return None

    def load_from_git(self, spec_id: str, commit: str) -> ApprovalManifest | None:
        """Load a manifest from a specific git commit (tamper-proof).

        The agent may modify files on disk, but the builder reads from
        git objects to ensure the manifest reflects what was approved.

        Args:
            spec_id: The spec identifier (without .yaml extension).
            commit: The git commit SHA or ref to read from.

        Returns:
            ApprovalManifest or None if not found.
        """
        path = f".village/approvals/{spec_id}.yaml"
        try:
            result = subprocess.run(
                ["git", "show", f"{commit}:{path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            return self._parse(result.stdout, spec_id)
        except subprocess.CalledProcessError:
            logger.debug(f"Manifest {spec_id} not found at {commit}:{path}")
            return None
        except FileNotFoundError:
            logger.debug("git command not found")
            return None

    def _parse(self, yaml_content: str, spec_id: str) -> ApprovalManifest | None:
        """Parse YAML content into an ApprovalManifest."""
        try:
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                logger.warning(f"Manifest {spec_id} content is not a mapping")
                return None

            version = data.get("version", 1)
            if not isinstance(version, int) or version < 1:
                logger.warning(f"Invalid manifest version for {spec_id}: {version}")
                return None

            return ApprovalManifest(
                version=version,
                spec_id=spec_id,
                allowed_commands=data.get("allowed_commands"),
                allowed_scripts=data.get("allowed_scripts"),
                allowed_paths=data.get("allowed_paths"),
                disallowed_content=data.get("disallowed_content"),
                test_required=data.get("test_required", True),
                filename_casing=data.get("filename_casing"),
            )
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse manifest {spec_id}: {e}")
            return None
