"""Tests for ACP permission policy system."""

import json
from pathlib import Path

import pytest

from village.acp.permissions import (
    PermissionDecision,
    PermissionPolicy,
    load_permission_policy,
)


class TestPermissionDecision:
    """Test PermissionDecision enum."""

    def test_decision_values(self):
        """Test enum values."""
        assert PermissionDecision.ALLOW.value == "allow"
        assert PermissionDecision.DENY.value == "deny"
        assert PermissionDecision.PROMPT.value == "prompt"


class TestPermissionPolicyInit:
    """Test PermissionPolicy initialization."""

    def test_empty_policy(self):
        """Test creating empty policy."""
        policy = PermissionPolicy()

        assert policy.allow == []
        assert policy.deny == []
        assert policy.prompt == []

    def test_policy_with_lists(self):
        """Test creating policy with lists."""
        policy = PermissionPolicy(
            allow=["filesystem.read"],
            deny=["filesystem.write"],
            prompt=["terminal.*"],
        )

        assert policy.allow == ["filesystem.read"]
        assert policy.deny == ["filesystem.write"]
        assert policy.prompt == ["terminal.*"]


class TestDefaultAutoApprove:
    """Test default_auto_approve class method."""

    def test_auto_approve_allows_everything(self):
        """Test auto-approve policy allows all operations."""
        policy = PermissionPolicy.default_auto_approve()

        assert policy.check_permission("filesystem.read") == PermissionDecision.ALLOW
        assert policy.check_permission("filesystem.write") == PermissionDecision.ALLOW
        assert policy.check_permission("terminal.create") == PermissionDecision.ALLOW
        assert policy.check_permission("any.operation") == PermissionDecision.ALLOW

    def test_auto_approve_structure(self):
        """Test auto-approve policy structure."""
        policy = PermissionPolicy.default_auto_approve()

        assert policy.allow == ["*"]
        assert policy.deny == []
        assert policy.prompt == []


class TestFromFile:
    """Test from_file class method."""

    def test_load_valid_policy(self, tmp_path: Path):
        """Test loading valid policy file."""
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "allow": ["filesystem.read", "filesystem.list"],
                    "deny": ["filesystem.write"],
                    "prompt": ["terminal.create"],
                }
            )
        )

        policy = PermissionPolicy.from_file(policy_file)

        assert policy.allow == ["filesystem.read", "filesystem.list"]
        assert policy.deny == ["filesystem.write"]
        assert policy.prompt == ["terminal.create"]

    def test_load_missing_file(self, tmp_path: Path):
        """Test loading missing policy file."""
        policy_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Permission policy file not found"):
            PermissionPolicy.from_file(policy_file)

    def test_load_invalid_json(self, tmp_path: Path):
        """Test loading invalid JSON."""
        policy_file = tmp_path / "invalid.json"
        policy_file.write_text("not valid json")

        with pytest.raises(json.JSONDecodeError):
            PermissionPolicy.from_file(policy_file)

    def test_load_non_object_json(self, tmp_path: Path):
        """Test loading JSON that's not an object."""
        policy_file = tmp_path / "array.json"
        policy_file.write_text(json.dumps(["allow", "deny"]))

        with pytest.raises(ValueError, match="must contain a JSON object"):
            PermissionPolicy.from_file(policy_file)

    def test_load_with_missing_keys(self, tmp_path: Path):
        """Test loading policy with missing keys."""
        policy_file = tmp_path / "partial.json"
        policy_file.write_text(json.dumps({"allow": ["*"]}))

        policy = PermissionPolicy.from_file(policy_file)

        assert policy.allow == ["*"]
        assert policy.deny == []
        assert policy.prompt == []

    def test_load_with_non_list_allow(self, tmp_path: Path):
        """Test loading policy with non-list allow."""
        policy_file = tmp_path / "bad_allow.json"
        policy_file.write_text(json.dumps({"allow": "not a list"}))

        with pytest.raises(ValueError, match="'allow' must be a list"):
            PermissionPolicy.from_file(policy_file)

    def test_load_with_non_list_deny(self, tmp_path: Path):
        """Test loading policy with non-list deny."""
        policy_file = tmp_path / "bad_deny.json"
        policy_file.write_text(json.dumps({"deny": "not a list"}))

        with pytest.raises(ValueError, match="'deny' must be a list"):
            PermissionPolicy.from_file(policy_file)

    def test_load_with_non_list_prompt(self, tmp_path: Path):
        """Test loading policy with non-list prompt."""
        policy_file = tmp_path / "bad_prompt.json"
        policy_file.write_text(json.dumps({"prompt": "not a list"}))

        with pytest.raises(ValueError, match="'prompt' must be a list"):
            PermissionPolicy.from_file(policy_file)

    def test_load_with_non_string_items(self, tmp_path: Path):
        """Test loading policy with non-string items."""
        policy_file = tmp_path / "bad_items.json"
        policy_file.write_text(json.dumps({"allow": [1, 2, 3]}))

        with pytest.raises(ValueError, match="'allow\\[0\\]' must be a string"):
            PermissionPolicy.from_file(policy_file)


class TestMatchOperation:
    """Test match_operation method."""

    def test_exact_match(self):
        """Test exact pattern matching."""
        policy = PermissionPolicy(allow=["filesystem.read"])

        assert policy.match_operation("filesystem.read", policy.allow) is True
        assert policy.match_operation("filesystem.write", policy.allow) is False

    def test_wildcard_match(self):
        """Test wildcard pattern matching."""
        policy = PermissionPolicy(allow=["*"])

        assert policy.match_operation("filesystem.read", policy.allow) is True
        assert policy.match_operation("filesystem.write", policy.allow) is True
        assert policy.match_operation("terminal.create", policy.allow) is True

    def test_prefix_wildcard_match(self):
        """Test prefix wildcard pattern matching."""
        policy = PermissionPolicy(allow=["filesystem.*"])

        assert policy.match_operation("filesystem.read", policy.allow) is True
        assert policy.match_operation("filesystem.write", policy.allow) is True
        assert policy.match_operation("filesystem.list", policy.allow) is True
        assert policy.match_operation("terminal.create", policy.allow) is False

    def test_multiple_patterns(self):
        """Test matching against multiple patterns."""
        policy = PermissionPolicy(allow=["filesystem.read", "terminal.*"])

        assert policy.match_operation("filesystem.read", policy.allow) is True
        assert policy.match_operation("terminal.create", policy.allow) is True
        assert policy.match_operation("terminal.kill", policy.allow) is True
        assert policy.match_operation("filesystem.write", policy.allow) is False

    def test_empty_pattern_list(self):
        """Test matching against empty list."""
        policy = PermissionPolicy()

        assert policy.match_operation("any.operation", []) is False


class TestCheckPermission:
    """Test check_permission method."""

    def test_deny_takes_precedence(self):
        """Test deny list is checked first."""
        policy = PermissionPolicy(
            allow=["*"],
            deny=["filesystem.write"],
            prompt=["filesystem.write"],
        )

        assert policy.check_permission("filesystem.write") == PermissionDecision.DENY

    def test_allow_after_deny_check(self):
        """Test allow list is checked after deny."""
        policy = PermissionPolicy(
            allow=["filesystem.read"],
            deny=[],
        )

        assert policy.check_permission("filesystem.read") == PermissionDecision.ALLOW

    def test_prompt_after_allow_check(self):
        """Test prompt list is checked after allow."""
        policy = PermissionPolicy(
            allow=[],
            deny=[],
            prompt=["terminal.create"],
        )

        assert policy.check_permission("terminal.create") == PermissionDecision.PROMPT

    def test_default_deny(self):
        """Test unknown operations are denied by default."""
        policy = PermissionPolicy()

        assert policy.check_permission("unknown.operation") == PermissionDecision.DENY

    def test_full_policy_order(self):
        """Test full policy with all lists."""
        policy = PermissionPolicy(
            allow=["filesystem.read", "filesystem.list"],
            deny=["filesystem.write", "filesystem.delete"],
            prompt=["terminal.*"],
        )

        assert policy.check_permission("filesystem.read") == PermissionDecision.ALLOW
        assert policy.check_permission("filesystem.list") == PermissionDecision.ALLOW
        assert policy.check_permission("filesystem.write") == PermissionDecision.DENY
        assert policy.check_permission("filesystem.delete") == PermissionDecision.DENY
        assert policy.check_permission("terminal.create") == PermissionDecision.PROMPT
        assert policy.check_permission("terminal.kill") == PermissionDecision.PROMPT
        assert policy.check_permission("unknown.operation") == PermissionDecision.DENY

    def test_wildcard_in_policy(self):
        """Test wildcard patterns in policy."""
        policy = PermissionPolicy(
            allow=["filesystem.*"],
            deny=["terminal.*"],
        )

        assert policy.check_permission("filesystem.read") == PermissionDecision.ALLOW
        assert policy.check_permission("filesystem.write") == PermissionDecision.ALLOW
        assert policy.check_permission("terminal.create") == PermissionDecision.DENY
        assert policy.check_permission("terminal.kill") == PermissionDecision.DENY


class TestLoadPermissionPolicy:
    """Test load_permission_policy function."""

    def test_auto_mode(self):
        """Test auto mode returns auto-approve policy."""
        policy = load_permission_policy(
            mode="auto",
            policy_file=None,
            village_dir=Path("/tmp"),
        )

        assert policy.check_permission("any.operation") == PermissionDecision.ALLOW

    def test_policy_mode_with_file(self, tmp_path: Path):
        """Test policy mode with valid file."""
        policy_file = tmp_path / "custom.json"
        policy_file.write_text(
            json.dumps(
                {
                    "allow": ["filesystem.*"],
                    "deny": ["terminal.*"],
                }
            )
        )

        policy = load_permission_policy(
            mode="policy",
            policy_file=str(policy_file),
            village_dir=tmp_path,
        )

        assert policy.check_permission("filesystem.read") == PermissionDecision.ALLOW
        assert policy.check_permission("terminal.create") == PermissionDecision.DENY

    def test_policy_mode_with_relative_path(self, tmp_path: Path):
        """Test policy mode with relative path."""
        village_dir = tmp_path / ".village"
        village_dir.mkdir()
        policy_file = village_dir / "permissions.json"
        policy_file.write_text(
            json.dumps(
                {
                    "allow": ["test.operation"],
                }
            )
        )

        policy = load_permission_policy(
            mode="policy",
            policy_file="permissions.json",
            village_dir=village_dir,
        )

        assert policy.check_permission("test.operation") == PermissionDecision.ALLOW

    def test_policy_mode_missing_file(self):
        """Test policy mode with missing file."""
        with pytest.raises(FileNotFoundError):
            load_permission_policy(
                mode="policy",
                policy_file="/nonexistent/policy.json",
                village_dir=Path("/tmp"),
            )

    def test_policy_mode_no_file_specified(self):
        """Test policy mode without file specified."""
        policy = load_permission_policy(
            mode="policy",
            policy_file=None,
            village_dir=Path("/tmp"),
        )

        assert policy.check_permission("any.operation") == PermissionDecision.DENY

    def test_unknown_mode_defaults_deny_all(self):
        """Test unknown mode defaults to deny-all."""
        policy = load_permission_policy(
            mode="unknown",
            policy_file=None,
            village_dir=Path("/tmp"),
        )

        assert policy.check_permission("any.operation") == PermissionDecision.DENY
