"""Build loop integration tests — tests that tie together multiple engine modules.

Covers BUILD_COMMIT freeze, git_show tamper-proofing, verification integration,
and plan protocol round-trips.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from village.execution.protocol import ExecutionResult, PlanProtocol
from village.execution.refs import freeze_build_commit, git_show
from village.execution.verify import (
    format_violations_for_inspect,
    inject_violation_notes,
    run_verification,
)
from village.rules.schema import (
    FilenameConfig,
    ForbiddenContentRule,
    RulesConfig,
    TddConfig,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a git repository with an initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    # Use lowercase filename to pass snake_case checks in verification tests
    readme = repo / "readme.md"
    readme.write_text("# Test Repo")
    subprocess.run(["git", "add", "readme.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


# ═══════════════════════════════════════════════════════════════════════════
# BUILD_COMMIT freeze tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildCommitFreeze:
    """BUILD_COMMIT freeze ensures config is tamper-proof."""

    def test_freeze_returns_valid_hash(self, git_repo: Path):
        """freeze_build_commit returns a valid 40-char SHA-1 hash."""
        commit = freeze_build_commit(git_repo)
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit)

    def test_freeze_returns_same_hash_for_unchanged_repo(self, git_repo: Path):
        """Freezing twice on an unchanged repo returns the same hash."""
        first = freeze_build_commit(git_repo)
        second = freeze_build_commit(git_repo)
        assert first == second

    def test_freeze_fails_on_non_git_dir(self, tmp_path: Path):
        """freeze_build_commit raises RuntimeError in a non-git directory.

        The directory must exist but not be a git repo (otherwise
        subprocess will raise FileNotFoundError for a missing cwd).
        """
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()
        with pytest.raises(RuntimeError):
            freeze_build_commit(empty_dir)

    def test_freeze_captures_state_before_change(self, git_repo: Path):
        """The frozen commit does not include uncommitted changes."""
        build_commit = freeze_build_commit(git_repo)

        # Make uncommitted changes
        (git_repo / "new_file.py").write_text("# new file")

        # The frozen commit should not include the new file
        content = git_show(git_repo, build_commit, "new_file.py")
        assert content is None

    def test_freeze_captures_state_after_commit(self, git_repo: Path):
        """After committing, the freeze captures the latest state."""
        (git_repo / "version2.py").write_text("# v2")
        subprocess.run(["git", "add", "version2.py"], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "v2"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        build_commit = freeze_build_commit(git_repo)
        content = git_show(git_repo, build_commit, "version2.py")
        assert content is not None
        assert "# v2" in content


# ═══════════════════════════════════════════════════════════════════════════
# git_show tamper-proof tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGitShowTamperProof:
    """git_show reads from git objects, not the filesystem."""

    def test_git_show_returns_committed_content(self, git_repo: Path):
        """git_show returns content as it exists in the commit."""
        readme = git_repo / "readme.md"
        original = readme.read_text()

        commit = freeze_build_commit(git_repo)
        content = git_show(git_repo, commit, "readme.md")
        assert content is not None
        assert content.strip() == original.strip()

    def test_git_show_differs_from_disk_after_modification(self, git_repo: Path):
        """git_show returns committed content even after disk modification."""
        commit = freeze_build_commit(git_repo)

        # Modify the file on disk
        readme = git_repo / "readme.md"
        readme.write_text("# MODIFIED ON DISK")

        # git_show should return the original committed content
        content = git_show(git_repo, commit, "readme.md")
        assert content is not None
        assert "# Test Repo" in content
        assert "MODIFIED ON DISK" not in content

    def test_git_show_returns_none_for_new_file_not_committed(self, git_repo: Path):
        """git_show returns None for files that don't exist in the commit."""
        commit = freeze_build_commit(git_repo)

        # Create a file but don't commit it
        (git_repo / "uncommitted.py").write_text("# new")

        content = git_show(git_repo, commit, "uncommitted.py")
        assert content is None

    def test_git_show_dot_village_rules(self, git_repo: Path):
        """git_show can read .village/rules.yaml from a commit."""
        # Add a config file and commit it
        config = git_repo / ".village" / "rules.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("version: 1\ncontent_rules: []\n")
        subprocess.run(["git", "add", ".village/rules.yaml"], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add rules"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        commit = freeze_build_commit(git_repo)

        # Modify on disk
        config.write_text("version: 999\nhacked: true\n")

        # git_show should return the original
        content = git_show(git_repo, commit, ".village/rules.yaml")
        assert content is not None
        assert "version: 1" in content
        assert "hacked" not in content


# ═══════════════════════════════════════════════════════════════════════════
# Verification integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVerificationIntegration:
    """Integration tests for run_verification()."""

    def test_verification_clean_worktree(self, git_repo: Path):
        """Clean worktree passes all configured checks."""
        rules = RulesConfig(
            version=1,
            content_rules=[
                ForbiddenContentRule(match="TODO", reason="No TODOs"),
            ],
            filename=FilenameConfig(casing="snake_case"),
            tdd=TddConfig(enabled=True, test_dirs=["tests/"]),
        )
        results = run_verification(git_repo, spec_id="test", rules=rules)
        assert all(r.passed for r in results)

    def test_verification_with_content_violations(self, tmp_path: Path):
        """Worktree with forbidden content fails content check."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "readme.md").write_text("# Test")
        subprocess.run(["git", "add", "readme.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        # Add file with secret
        (repo / "config.py").write_text("password=secret\n")

        rules = RulesConfig(
            version=1,
            content_rules=[
                ForbiddenContentRule(match="password=", reason="No passwords"),
            ],
        )
        results = run_verification(repo, spec_id="test", rules=rules)
        content_result = [r for r in results if r.rule_name == "content_rules"]
        assert len(content_result) >= 1
        assert content_result[0].passed is False

    def test_verification_tdd_fails(self, tmp_path: Path):
        """Worktree without matching tests fails TDD verification."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "readme.md").write_text("# Test")
        subprocess.run(["git", "add", "readme.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        # Add source file WITHOUT a test — stage but do NOT commit it
        # (run_verification uses git diff HEAD which includes staged files)
        src = repo / "src" / "service.py"
        src.parent.mkdir()
        src.write_text("class Service: pass\n")
        subprocess.run(["git", "add", "src/service.py"], cwd=repo, check=True, capture_output=True)

        rules = RulesConfig(
            version=1,
            tdd=TddConfig(enabled=True, test_dirs=["tests/"]),
        )
        results = run_verification(repo, spec_id="test", rules=rules)
        tdd_results = [r for r in results if r.rule_name == "tdd"]
        assert len(tdd_results) >= 1
        assert tdd_results[0].passed is False

    def test_verification_casing_fails(self, tmp_path: Path):
        """Bad filename casing fails verification."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "readme.md").write_text("# Test")
        subprocess.run(["git", "add", "readme.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        # Add a CamelCase file — stage but do NOT commit it
        # (run_verification uses git diff HEAD which includes staged files)
        (repo / "BadCase.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "BadCase.py"], cwd=repo, check=True, capture_output=True)

        rules = RulesConfig(
            version=1,
            filename=FilenameConfig(casing="snake_case"),
        )
        results = run_verification(repo, spec_id="test", rules=rules)
        casing_results = [r for r in results if r.rule_name == "filename_casing"]
        assert len(casing_results) >= 1
        assert casing_results[0].passed is False

    def test_verification_no_rules_no_crash(self, git_repo: Path):
        """No rules config returns empty results without crashing."""
        results = run_verification(git_repo, spec_id="test", rules=None)
        assert results == []

    def test_verification_violation_formatting(self):
        """format_violations_for_inspect produces readable output."""
        from village.execution.scanner import ScanViolation

        violations = [
            ScanViolation(
                rule="content",
                message="Found secret",
                file_path=Path("config.py"),
                line=5,
                pattern="secret",
            ),
            ScanViolation(
                rule="filename",
                message="Bad casing",
                file_path=Path("BadFile.py"),
                pattern="snake_case",
            ),
        ]
        formatted = format_violations_for_inspect(violations)
        assert "## Inspect Notes" in formatted
        assert "config.py" in formatted
        assert "BadFile.py" in formatted
        assert "content" in formatted
        assert "filename" in formatted

    def test_verification_inject_notes(self, tmp_path: Path):
        """inject_violation_notes appends to the spec file."""
        from village.execution.scanner import ScanViolation

        spec = tmp_path / "spec.md"
        spec.write_text("# My Spec\n\nDo something\n")

        violations = [
            ScanViolation(rule="content", message="Found secret", file_path=Path("config.py"), line=5),
        ]
        inject_violation_notes(spec, violations)
        content = spec.read_text()
        assert "## Inspect Notes" in content
        assert "Found secret" in content
        assert "# My Spec" in content  # Original content preserved

    def test_verification_inject_notes_replaces_existing(self, tmp_path: Path):
        """Replace existing Inspect Notes section when injecting again."""
        from village.execution.scanner import ScanViolation

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n\n## Inspect Notes\n\nOld notes\n\n---\n\n")

        violations = [
            ScanViolation(rule="content", message="New issue", file_path=Path("x.py")),
        ]
        inject_violation_notes(spec, violations)
        content = spec.read_text()
        assert "New issue" in content
        assert "Old notes" not in content  # Should be replaced


# ═══════════════════════════════════════════════════════════════════════════
# Plan protocol round-trip tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanProtocolRoundTrip:
    """Tests for PlanProtocol parse/format round-trips."""

    def test_plan_round_trip_single_action(self):
        """Parse a plan and verify the actions are structured correctly."""
        plan_text = '<plan>[{"action": "bash", "command": "pytest tests/"}]</plan>'
        plan = PlanProtocol.parse_plan(plan_text)
        assert plan is not None
        assert len(plan.actions) == 1
        assert plan.actions[0].action == "bash"
        assert plan.actions[0].command == "pytest tests/"
        assert plan.actions[0].id == 0

    def test_plan_round_trip_multiple_actions(self):
        """Parse a multi-action plan."""
        plan_text = """<plan>
[
  {"action": "write", "path": "src/foo.py", "content": "x = 1", "id": 0},
  {"action": "bash", "command": "ruff check src/", "id": 1}
]
</plan>"""
        plan = PlanProtocol.parse_plan(plan_text)
        assert plan is not None
        assert len(plan.actions) == 2
        assert plan.actions[0].action == "write"
        assert plan.actions[0].path == "src/foo.py"
        assert plan.actions[1].action == "bash"
        assert plan.actions[1].command == "ruff check src/"

    def test_executed_format_structure(self):
        """Format executed results and verify the output structure."""
        results = [
            ExecutionResult(id=0, status="ok", stdout="1 passed"),
            ExecutionResult(id=1, status="blocked", reason="Not allowed"),
        ]
        output = PlanProtocol.format_executed(results)
        assert output.startswith("<executed>")
        assert output.endswith("</executed>")
        assert '"id": 0' in output
        assert '"id": 1' in output
        assert '"status": "ok"' in output
        assert '"status": "blocked"' in output

    def test_executed_format_json_parseable(self):
        """The executed output should be valid JSON inside the tags."""
        results = [
            ExecutionResult(id=0, status="ok", stdout="test output"),
        ]
        import json
        import re

        output = PlanProtocol.format_executed(results)
        match = re.search(r"<executed>\n(.*)\n</executed>", output, re.DOTALL)
        assert match is not None
        data = json.loads(match.group(1))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 0
        assert data[0]["status"] == "ok"

    def test_contract_section_includes_protocol_instructions(self):
        """The contract section includes execution protocol instructions."""
        contract = PlanProtocol.format_contract_section()
        assert "Execution Protocol" in contract
        assert "<plan>" in contract
        assert "<executed>" in contract
        assert "bash" in contract
        assert "write" in contract
        assert "Do NOT run git commit/push directly" in contract

    def test_parse_plan_with_extra_text(self):
        """Parse a plan from agent output with surrounding text."""
        text = """Let me think about this...

I need to create a new file and run tests.

<plan>
[
  {"action": "write", "path": "src/utils.py", "content": "def add(a, b): return a + b"},
  {"action": "bash", "command": "pytest tests/"}
]
</plan>

That should do it."""
        plan = PlanProtocol.parse_plan(text)
        assert plan is not None
        assert len(plan.actions) == 2
        assert plan.actions[0].path == "src/utils.py"
        assert plan.actions[1].command == "pytest tests/"

    def test_parse_plan_empty_json_array(self):
        """Parse a plan with an empty JSON array."""
        text = "<plan>[]</plan>"
        plan = PlanProtocol.parse_plan(text)
        assert plan is not None
        assert len(plan.actions) == 0

    def test_parse_plan_with_ids(self):
        """Parse a plan with explicit IDs."""
        text = '<plan>[{"action": "bash", "command": "ls", "id": 42}]</plan>'
        plan = PlanProtocol.parse_plan(text)
        assert plan is not None
        assert len(plan.actions) == 1
        assert plan.actions[0].id == 42
