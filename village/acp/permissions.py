"""Permission policy system for ACP client.

Loads policy from JSON file and matches operations against rules.
"""

import fnmatch
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PermissionDecision(Enum):
    """Permission decision types."""

    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"


@dataclass
class PermissionPolicy:
    """Permission policy loaded from JSON file."""

    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    prompt: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, policy_path: Path) -> "PermissionPolicy":
        """Load policy from JSON file.

        Args:
            policy_path: Path to policy JSON file

        Returns:
            PermissionPolicy instance

        Raises:
            FileNotFoundError: If policy file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
            ValueError: If policy format is invalid
        """
        if not policy_path.exists():
            raise FileNotFoundError(f"Permission policy file not found: {policy_path}")

        with open(policy_path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Policy file must contain a JSON object")

        allow = data.get("allow", [])
        deny = data.get("deny", [])
        prompt = data.get("prompt", [])

        if not isinstance(allow, list):
            raise ValueError("'allow' must be a list")
        if not isinstance(deny, list):
            raise ValueError("'deny' must be a list")
        if not isinstance(prompt, list):
            raise ValueError("'prompt' must be a list")

        for lst, name in [(allow, "allow"), (deny, "deny"), (prompt, "prompt")]:
            for i, item in enumerate(lst):
                if not isinstance(item, str):
                    raise ValueError(f"'{name}[{i}]' must be a string")

        logger.info(f"Loaded permission policy from {policy_path}")
        logger.debug(f"Policy: allow={allow}, deny={deny}, prompt={prompt}")

        return cls(allow=allow, deny=deny, prompt=prompt)

    @classmethod
    def default_auto_approve(cls) -> "PermissionPolicy":
        """Create a policy that auto-approves everything.

        Returns:
            PermissionPolicy that allows all operations
        """
        return cls(allow=["*"], deny=[], prompt=[])

    def match_operation(self, operation: str, patterns: list[str]) -> bool:
        """Check if operation matches any pattern in list.

        Supports glob-style wildcards:
        - "*" matches anything
        - "filesystem.*" matches all filesystem operations
        - "filesystem.read" matches exact operation

        Args:
            operation: Operation to check (e.g., "filesystem.read")
            patterns: List of patterns to match against

        Returns:
            True if operation matches any pattern
        """
        for pattern in patterns:
            if fnmatch.fnmatch(operation, pattern):
                return True
        return False

    def check_permission(self, operation: str) -> PermissionDecision:
        """Check permission for an operation.

        Matching order:
        1. Check deny list -> DENY
        2. Check allow list -> ALLOW
        3. Check prompt list -> PROMPT
        4. Default -> DENY

        Args:
            operation: Operation to check (e.g., "filesystem.read")

        Returns:
            PermissionDecision indicating the action to take
        """
        if self.match_operation(operation, self.deny):
            logger.debug(f"Operation '{operation}' denied by policy")
            return PermissionDecision.DENY

        if self.match_operation(operation, self.allow):
            logger.debug(f"Operation '{operation}' allowed by policy")
            return PermissionDecision.ALLOW

        if self.match_operation(operation, self.prompt):
            logger.debug(f"Operation '{operation}' requires prompt by policy")
            return PermissionDecision.PROMPT

        logger.debug(f"Operation '{operation}' denied by default")
        return PermissionDecision.DENY


def load_permission_policy(
    mode: str,
    policy_file: str | Path | None,
    village_dir: Path,
) -> PermissionPolicy:
    """Load permission policy based on mode and config.

    Args:
        mode: Permission mode ("auto" or "policy")
        policy_file: Path to policy file (relative to village_dir or absolute)
        village_dir: Village configuration directory

    Returns:
        PermissionPolicy instance
    """
    if mode == "auto":
        logger.debug("Using auto-approve permission mode")
        return PermissionPolicy.default_auto_approve()

    if mode != "policy":
        logger.warning(f"Unknown permission mode '{mode}', defaulting to deny-all")
        return PermissionPolicy(allow=[], deny=["*"], prompt=[])

    if not policy_file:
        logger.warning("Policy mode enabled but no policy file specified, denying all")
        return PermissionPolicy(allow=[], deny=["*"], prompt=[])

    policy_path = Path(policy_file)
    if not policy_path.is_absolute():
        policy_path = village_dir / policy_file

    try:
        return PermissionPolicy.from_file(policy_path)
    except FileNotFoundError:
        logger.error(f"Permission policy file not found: {policy_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in permission policy file: {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid permission policy format: {e}")
        raise
